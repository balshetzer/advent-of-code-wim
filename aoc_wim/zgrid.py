import logging
import string
from collections import ChainMap
from collections import deque
import numpy as np
import networkx as nx


log = logging.getLogger(__name__)


dzs = [-1j, 1, 1j, -1]


class ZDict(dict):

    def __init__(self, func):
        self.func = func

    def __missing__(self, z):
        if not isinstance(z, (int, complex, float)):
            log.error("ZDict does not support key %r", z)
            raise NotImplementedError
        self[z] = self.func(z)
        return self[z]


class ZGrid:

    dzs = ChainMap(
        dict(zip(dzs, dzs)),
        dict(zip("^>v<", dzs)),
        dict(zip("up right down left".split(), dzs)),
        dict(zip("up right down left".upper().split(), dzs)),
        dict(zip("URDL", dzs)),
        dict(zip("NESW", dzs)),
    )
    U = N = up = north = -1j
    R = E = right = east = 1
    D = S = down = south = 1j
    L = W = left = west = -1

    turn_right = 1j
    turn_left = -1j
    turn_around = -1

    def __init__(self, initial_data=None, on="#", off="."):
        self.on = on
        self.off = off
        self.d = d = {}
        if initial_data is not None:
            if isinstance(initial_data, str):
                for row, line in enumerate(initial_data.splitlines()):
                    for col, char in enumerate(line):
                        d[col + row*1j] = char
            elif callable(initial_data):
                self.d = ZDict(func=initial_data)
            elif isinstance(initial_data, dict):
                self.d = initial_data

    def __setitem__(self, key, value):
        self.d[key] = value

    def __getitem__(self, key):
        return self.d[key]

    def __delitem__(self, key):
        del self.d[key]

    def __contains__(self, item):
        return item in self.d

    def __iter__(self):
        return iter(self.d)

    def __len__(self):
        return len(self.d)

    def items(self):
        return self.d.items()

    def values(self):
        return self.d.values()

    def get(self, k, default=None):
        return self.d.get(k, default)

    def z(self, val, first=True):
        zs = []
        for k, v in self.items():
            if v == val:
                if first:
                    return k
                zs.append(k)
        return zs

    def near(self, z, n=4):
        if n == 4:
            return [z - 1j, z + 1, z + 1j, z - 1]
        elif n == 8:
            return [
                z - 1 - 1j, z - 1j, z + 1 - 1j,
                z - 1, z + 1,
                z - 1 + 1j, z + 1j, z + 1 + 1j,
            ]

    def draw(self, overlay=None, window=None, clear=False, pretty=True):
        if window is None:
            d = self.d
        else:
            if isinstance(window, complex):
                window = zrange(window + 1 + 1j)
            d = {z: self[z] for z in window}
        if overlay is not None:
            d = {**self.d, **overlay}
        dump_grid(d, clear=clear, pretty=pretty)

    def translate(self, table):
        for z in self.d:
            if self.d[z] in table:
                self.d[z] = table[self.d[z]]

    @property
    def n_on(self):
        return sum(1 for val in self.d.values() if val == self.on)

    def n_on_near(self, z0, n=4):
        return sum(1 for z in self.near(z0, n=n) if self.d.get(z) == self.on)

    def __array__(self):
        """makes np.array(zgrid) work"""
        zs = np.array(list(self.d))
        xs = zs.real.astype(int)
        ys = zs.imag.astype(int)
        vs = np.array(list(self.d.values()))
        w = xs.ptp() + 1
        h = ys.ptp() + 1
        full = np.full((h, w), fill_value=self.off, dtype=vs.dtype)
        full[ys - ys.min(), xs - xs.min()] = vs
        return full

    def graph(self, extra=()):
        """connected components"""
        node_glyphs = {self.on}.union(extra)
        g = nx.Graph()
        g.extra = {}
        for pos, glyph in self.d.items():
            if glyph in node_glyphs:
                g.add_node(pos)
                if glyph != self.on:
                    g.extra[glyph] = pos
                right = pos + 1
                down = pos + 1j
                if self.d.get(right) in node_glyphs:
                    g.add_edge(pos, right)
                if self.d.get(down) in node_glyphs:
                    g.add_edge(pos, down)
        return g

    def path(self, z, z0=0):
        g = self.graph()
        return nx.shortest_path(g, z0, z)

    def path_length(self, z, z0=0):
        g = self.graph()
        return nx.shortest_path_length(g, z0, z)

    def draw_path(self, z, z0=0, glyph="x", clear=False, pretty=True):
        path = self.path(z, z0)
        overlay = {}.fromkeys(path, glyph)
        overlay[path[0]] = "O"
        overlay[path[-1]] = "T"
        self.draw(overlay=overlay, clear=clear, pretty=pretty)

    def bfs(self, target=None, z0=0, max_depth=None):
        """returns a dict of connected nodes vs depth up to max_depth"""
        g0 = self[z0]
        if g0 != self.on:
            log.error("Expected initial glyph %r, got %r", self.on, g0)
            raise NotImplementedError
        seen = {}
        queue = deque([(z0, 0)])
        while queue:
            z0, depth = queue.popleft()
            if max_depth is not None and depth > max_depth:
                return seen
            if z0 not in seen:
                seen[z0] = depth
                if target is not None and z0 == target:
                    return seen
                for z in self.near(z0):
                    if z in seen:
                        continue
                    try:
                        g = self[z]
                    except KeyError:
                        continue
                    if g == self.on:
                        queue.append((z, depth + 1))
        return seen

    @property
    def top_left(self):
        return min(self.d, key=lambda z: (z.imag, z.real))

    @property
    def left_bottom(self):
        return min(self.d, key=lambda z: (z.real, -z.imag))

    @property
    def bottom_right(self):
        return max(self.d, key=lambda z: (z.imag, z.real))

    @property
    def right_top(self):
        return max(self.d, key=lambda z: (z.real, -z.imag))

    @property
    def width(self):
        return int(self.right_top.real - self.left_bottom.real) + 1

    @property
    def height(self):
        return int(self.bottom_right.imag - self.top_left.imag) + 1


def dump_grid(g, clear=False, pretty=True):
    transform = {
        "#": "⬛",
        ".": "  ",
        "O": "🤖",
        "T": "🥇",
        "x": "👣",
        ">": "➡️ ",
        "<": "⬅️ ",
        "^": "⬆️ ",
        "v": "⬇️ ",
        "@": "@️ ",
        0: "  ",
        1: "⬛",
    }
    transform.update({x: x + " " for x in string.ascii_letters if x not in transform})
    empty = "  " if pretty else "."
    print()
    xs = [int(z.real) for z in g]
    ys = [int(z.imag) for z in g]
    cols = range(min(xs), max(xs) + 1)
    rows = range(min(ys), max(ys) + 1)
    if clear:
        print("\033c")
    for row in rows:
        print(f"{row:>5d} ", end="")
        for col in cols:
            glyph = g.get(col + row * 1j, empty)
            if pretty:
                glyph = transform.get(glyph, glyph)
            print(glyph, end="")
        print()
    W = len(cols)
    if pretty:
        W *= 2
    footer_left = f"{cols[0]}".ljust(W)
    footer_center = f"{cols[len(cols)//2]}".center(W)
    footer_right = f"{cols[-1]}".rjust(W)
    zf = zip(footer_left, footer_center, footer_right)
    footer = [next((x for x in iter([l, c, r]) if x != " "), " ") for (l, c, r) in zf]
    footer = "".join(footer)
    print(" " * 6 + footer)
    print()


def array2txt(a):
    a = a.astype(str)
    lines = ["".join(row) for row in a]
    txt = "\n".join(lines)
    return txt


def zrange(*args):
    if len(args) == 1:
        start = 0
        (stop,) = args
        step = 1 + 1j
    elif len(args) == 2:
        start, stop = args
        step = 1 + 1j
    elif len(args) == 3:
        start, stop, step = args
    else:
        raise TypeError(f"zrange expected 1-3 arguments, got {len(args)}")
    xs = range(int(start.real), int(stop.real), int(step.real))
    ys = range(int(start.imag), int(stop.imag), int(step.imag))
    return [complex(x, y) for y in ys for x in xs]
