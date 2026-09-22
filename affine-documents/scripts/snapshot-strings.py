#!/usr/bin/env python3
"""Decode an AFFiNE document snapshot blob into readable block strings.

A document's real content is a block tree, not the markdown any reader
reconstructs from it. Reading the block tree means reading the stored snapshot
blob, which is a binary y-octo stream: the useful content (block flavours such
as `sys:flavour`, property keys such as `prop:type` / `prop:text`, and the
inline latex sources) survives as plain ASCII runs separated by control bytes.

This script does the one job that must be exact — separating those runs from
the binary framing — and nothing else. Counting markers, comparing against a
source document, and deciding whether a document is damaged are judgement calls
that belong to the agent, which can pipe this output into `grep -c`.

Usage:
    snapshot-strings.py <blob-file>
    snapshot-strings.py --hex <hex-dump-file>
    snapshot-strings.py --hex -              # hex on stdin
    snapshot-strings.py <blob-file> --min 8  # only runs of at least 8 chars

Input is either the raw blob or its hex encoding (as returned by
`select encode(blob,'hex')`), one long line or wrapped.
"""

import argparse
import binascii
import sys

PRINTABLE = range(0x20, 0x7F)


def load_hex(text):
    compact = "".join(text.split())
    if len(compact) % 2:
        compact = compact[:-1]
    try:
        return binascii.unhexlify(compact)
    except binascii.Error as exc:
        sys.exit(f"error: input is not valid hex ({exc})")


def runs(data, minimum):
    out, current = [], []
    for byte in data:
        if byte in PRINTABLE:
            current.append(chr(byte))
        else:
            if len(current) >= minimum:
                out.append("".join(current))
            current = []
    if len(current) >= minimum:
        out.append("".join(current))
    return out


def main():
    parser = argparse.ArgumentParser(description="Decode an AFFiNE document snapshot blob into readable block strings.")
    parser.add_argument("blob", help="raw snapshot blob file, or '-' with --hex for stdin")
    parser.add_argument("--hex", action="store_true", help="the input file is a hex dump, not the raw blob")
    parser.add_argument("--min", type=int, default=3, help="minimum run length to print (default: 3)")
    args = parser.parse_args()

    if args.blob == "-":
        if not args.hex:
            sys.exit("error: reading stdin requires --hex")
        data = load_hex(sys.stdin.read())
    else:
        payload = open(args.blob, "rb").read()
        data = load_hex(payload.decode("ascii", "ignore")) if args.hex else payload

    print(f"{len(data)} bytes", file=sys.stderr)
    for run in runs(data, args.min):
        print(run)


if __name__ == "__main__":
    main()
