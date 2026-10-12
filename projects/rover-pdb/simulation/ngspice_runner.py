"""Run plain SPICE decks through KiCad's existing ngspice shared library.

No IC behavior is inferred or substituted. Interface: ngspice sharedspice.h.
Only standard-library Python is required; netlists and complete logs are retained.
"""
from __future__ import annotations
import csv
import ctypes as ct
import hashlib
import os
from pathlib import Path


class VectorInfo(ct.Structure):
    _fields_ = [("name", ct.c_char_p), ("type", ct.c_int), ("flags", ct.c_short),
                ("real", ct.POINTER(ct.c_double)), ("complex", ct.c_void_p),
                ("length", ct.c_int)]


class NgSpice:
    def __init__(self, dll: Path):
        self.dll_path = dll.resolve()
        self.dll_search = os.add_dll_directory(str(dll.parent)) if os.name == 'nt' else None
        self.lib = ct.CDLL(str(dll))
        self.messages = []
        self.exit_status = None
        send = ct.CFUNCTYPE(ct.c_int, ct.c_char_p, ct.c_int, ct.c_void_p)
        bye = ct.CFUNCTYPE(ct.c_int, ct.c_int, ct.c_bool, ct.c_bool, ct.c_int, ct.c_void_p)
        def text_cb(msg, ident, user):
            self.messages.append(msg.decode('utf-8', errors='replace'))
            return 0
        def bye_cb(status, immediate, quitexit, ident, user):
            self.exit_status = status
            return 0
        self.callbacks = (send(text_cb), send(lambda *_: 0), bye(bye_cb))
        self.lib.ngSpice_Init.argtypes = [ct.c_void_p] * 7
        self.lib.ngSpice_Init.restype = ct.c_int
        self.lib.ngSpice_Command.argtypes = [ct.c_char_p]
        self.lib.ngSpice_Command.restype = ct.c_int
        self.lib.ngSpice_Circ.argtypes = [ct.POINTER(ct.c_char_p)]
        self.lib.ngSpice_Circ.restype = ct.c_int
        self.lib.ngGet_Vec_Info.argtypes = [ct.c_char_p]
        self.lib.ngGet_Vec_Info.restype = ct.POINTER(VectorInfo)
        rc = self.lib.ngSpice_Init(*self.callbacks, None, None, None, None)
        if rc:
            raise RuntimeError(f'ngSpice_Init returned {rc}')
        self.command('version')
        self.version_log = '\n'.join(self.messages)

    def command(self, command):
        rc = self.lib.ngSpice_Command(command.encode())
        if rc:
            raise RuntimeError(f'ngspice command failed ({rc}): {command}')

    def run(self, deck: Path, vectors: list[str]):
        self.messages = []
        self.exit_status = None
        lines = [s.encode() for s in deck.read_text(encoding='utf-8').splitlines()]
        source = (ct.c_char_p * (len(lines) + 1))(*lines, None)
        rc = self.lib.ngSpice_Circ(source)
        try:
            if rc:
                raise RuntimeError(f'ngSpice_Circ returned {rc}')
            self.command('run')
            data = {}
            for name in vectors:
                ptr = self.lib.ngGet_Vec_Info(name.encode())
                if not ptr or not ptr.contents.real or ptr.contents.length < 1:
                    raise RuntimeError(f'Missing real vector: {name}')
                v = ptr.contents
                data[name] = [v.real[i] for i in range(v.length)]
            if self.exit_status is not None:
                raise RuntimeError(f'ngspice exited with {self.exit_status}')
            errors = [m for m in self.messages if any(k in m.lower() for k in
                      ('error:', 'fatal', 'timestep too small', 'simulation(s) aborted'))]
            if errors:
                raise RuntimeError('\n'.join(errors))
            if len({len(v) for v in data.values()}) != 1:
                raise RuntimeError('Vector lengths differ')
            with deck.with_suffix('.csv').open('w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(vectors)
                w.writerows(zip(*(data[k] for k in vectors)))
            return data
        finally:
            deck.with_suffix('.log').write_text('\n'.join(self.messages), encoding='utf-8')
            self.command('destroy all')

    def identity(self):
        return {'path': str(self.dll_path),
                'sha256': hashlib.sha256(self.dll_path.read_bytes()).hexdigest(),
                'version_log': self.version_log}
