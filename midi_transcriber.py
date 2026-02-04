#!/usr/bin/env python3
"""
MIDI Transcriber — outputs raw MIDI note numbers with timestamps and durations.

Output format (C++-style array):
  {index, midiNoteNumber, timeMSec, noteDuration}

Usage:
    python midi_transcriber.py <midi_file_path>
                               [--time-shift-ms MS] [--time-scale S]
                               [--min-duration-ms MS] [--limit N]
                               [--transpose N] [--clamp]
"""

import mido
import sys
import os
import argparse
import re
import subprocess
from dataclasses import dataclass
from typing import List, Tuple, Optional, Callable, Iterable

NOTE_MIN = 53
NOTE_MAX = 79
@dataclass
class MidiNote:
    """
    Compact event: no button mapping, no octave shift.
    """
    index: int = 0
    midiNoteNumber: int = 0
    timeMSec: int = 0
    noteDuration: int = 0


# -------- Helpers --------

def duration_to_fraction(duration_ms: int, tempo: int = 500000) -> str:
    """
    Rough bucket for the shortest note comment.
    """
    quarter_note_ms = tempo / 1000
    fractions = [
        (4.0, "1st"), (2.0, "1/2nd"), (1.0, "1/4th"),
        (0.5, "1/8th"), (0.25, "1/16th"), (0.125, "1/32nd"), (0.0625, "1/64th")
    ]
    best = "1/16th"
    mdiff = float("inf")
    for mult, name in fractions:
        diff = abs(duration_ms - quarter_note_ms * mult)
        if diff < mdiff:
            mdiff = diff
            best = name
    return best


def format_midi_notes_as_c_array(midi_notes: List[MidiNote], song_name: str) -> str:
    """
    Emit a C++ namespace with a const array of MidiNote.
    Fields: index, midiNoteNumber, timeMSec, noteDuration
    """
    lines = [
        '#include "MidiSong.h"',
        '',
        'namespace songs {',
        '  const MidiNote SONG[] = {'
    ]

    for i, n in enumerate(midi_notes):
        line = f"    {{{n.index}, {n.midiNoteNumber}, {n.timeMSec}, {n.noteDuration}}}"
        if i < len(midi_notes) - 1:
            line += ","
        lines.append(line)

    lines.append('  };')
    lines.append('')
    lines.append(f'  REGISTER_SONG({song_name}, SONG)')

    if midi_notes:
        shortest = min(n.noteDuration for n in midi_notes)
        lines.append(f'}} // {duration_to_fraction(shortest)}')
    else:
        lines.append('}')

    return "\n".join(lines)


# -------- Transform pipeline --------

@dataclass
class TransformOptions:
    time_shift_ms: int = 0
    time_scale: float = 1.0
    min_duration_ms: int = 0

Modifier = Callable[[MidiNote], MidiNote]


def apply_transforms(notes: Iterable[MidiNote],
                     opts: TransformOptions,
                     extra_modifiers: Iterable[Modifier] = ()) -> List[MidiNote]:
    out: List[MidiNote] = []
    for n in notes:
        m = MidiNote(**vars(n))  # copy

        if opts.time_scale != 1.0:
            m.timeMSec = int(round(m.timeMSec * opts.time_scale))
            m.noteDuration = int(round(m.noteDuration * opts.time_scale))

        if opts.time_shift_ms:
            m.timeMSec += opts.time_shift_ms

        if opts.min_duration_ms and m.noteDuration < opts.min_duration_ms:
            m.noteDuration = opts.min_duration_ms

        for mod in extra_modifiers:
            m = mod(m)

        out.append(m)

    if out:
        t0 = min(e.timeMSec for e in out)
        for e in out:
            e.timeMSec -= t0

    return out


# -------- MIDI parsing --------

def transcribe_midi(midi_file_path: str) -> List[Tuple[int, int, str]]:
    """
    Return events as (midi_note_number, timestamp_ms, "ON"/"OFF").
    """
    try:
        mid = mido.MidiFile(midi_file_path)
        note_events: List[Tuple[int, int, str]] = []

        ticks_per_beat = mid.ticks_per_beat
        default_tempo = 500000  # 120 BPM

        # Parse first two tracks; adjust if needed.
        for track in mid.tracks[:2]:
            cur_ticks = 0
            tempo = default_tempo
            for msg in track:
                cur_ticks += msg.time
                time_ms = int((cur_ticks * tempo) / (ticks_per_beat * 1000))

                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                elif msg.type == 'note_on' and msg.velocity > 0:
                    note_events.append((msg.note, time_ms, "ON"))
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    note_events.append((msg.note, time_ms, "OFF"))

        note_events.sort(key=lambda x: x[1])
        return note_events
    except Exception as e:
        print(f"Error processing MIDI file: {e}")
        return []


def convert_to_midi_notes(events: List[Tuple[int, int, str]],
                          limit: Optional[int] = None) -> List[MidiNote]:
    """
    Pair ON/OFF into MidiNote structs with raw MIDI note numbers.
    """
    out: List[MidiNote] = []
    active = {}  # note -> start_time_ms
    idx = 0

    for note_num, t_ms, state in events:
        if state == "ON":
            active[note_num] = t_ms
        elif state == "OFF" and note_num in active:
            start = active.pop(note_num)
            out.append(MidiNote(index=idx,
                                midiNoteNumber=note_num,
                                timeMSec=start,
                                noteDuration=t_ms - start))
            idx += 1
            if limit is not None and len(out) >= limit:
                break

    if out:
        t0 = min(n.timeMSec for n in out)
        for n in out:
            n.timeMSec -= t0

    return out


def filename_to_song_name(midi_file_path: str) -> str:
    base = os.path.splitext(os.path.basename(midi_file_path))[0]
    words = [w for w in re.split(r'[^A-Za-z0-9]+', base) if w]
    return "".join(w[:1].upper() + w[1:] for w in words) or "Song"


# -------- CLI --------

def main():
    parser = argparse.ArgumentParser(
        description='Convert MIDI to raw note numbers with timestamps/durations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Example: python midi_transcriber.py song.mid --time-scale 0.5 --min-duration-ms 40'
    )
    parser.add_argument('midi_file', help='Path to the MIDI file')
    parser.add_argument('--limit', type=int, metavar='N',
                        help='Limit number of notes (default: no limit)')
    parser.add_argument('--time-shift-ms', type=int, default=0,
                        help='Shift all start times by milliseconds')
    parser.add_argument('--time-scale', type=float, default=1.0,
                        help='Scale all times and durations, e.g., 0.5 = 2x speed')
    parser.add_argument('--min-duration-ms', type=int, default=0,
                        help='Floor any duration shorter than this value')
    parser.add_argument('--transpose', type=int, default=0,
                        help='Transpose all MIDI notes by N semitones (can be negative)')
    parser.add_argument('--clamp', action='store_true',
                        help=f'Clamp MIDI notes to [{NOTE_MIN}, {NOTE_MAX}] after transforms')

    args = parser.parse_args()
    midi_file_path = args.midi_file

    if not os.path.exists(midi_file_path):
        print(f"Error: File '{midi_file_path}' not found.")
        sys.exit(1)
    if not midi_file_path.lower().endswith(('.mid', '.midi')):
        print("Warning: file does not have .mid/.midi extension.")

    print(f"Transcribing MIDI file: {midi_file_path}")

    events = transcribe_midi(midi_file_path)
    if not events:
        print("No note events found or error occurred.")
        return

    notes = convert_to_midi_notes(events, args.limit)

    topts = TransformOptions(
        time_shift_ms=args.time_shift_ms,
        time_scale=args.time_scale,
        min_duration_ms=args.min_duration_ms,
    )

    extra_mods: List[Modifier] = []

    if args.transpose != 0:
        def make_transposer(semitones: int) -> Modifier:
            def _mod(n: MidiNote) -> MidiNote:
                # clamp to valid MIDI
                n.midiNoteNumber = max(0, min(127, n.midiNoteNumber + semitones))
                return n
            return _mod

        extra_mods.append(make_transposer(args.transpose))

    if args.clamp:
        def _clamp(n: MidiNote) -> MidiNote:
            n.midiNoteNumber = max(NOTE_MIN, min(NOTE_MAX, n.midiNoteNumber))
            return n
        extra_mods.append(_clamp)

    notes = apply_transforms(notes, topts, extra_mods)

    song_name = filename_to_song_name(midi_file_path)
    out_txt = format_midi_notes_as_c_array(notes, song_name)
    print(out_txt)

    output_filename = os.path.splitext(midi_file_path)[0] + "_transcription.txt"
    with open(output_filename, 'w') as f:
        f.write(out_txt)
    print(f"\nTranscription saved to: {output_filename}")
    try:
        subprocess.run(["pbcopy"], input=out_txt, text=True, check=True)
        print("Transcription copied to clipboard.")
    except Exception as e:
        print(f"Warning: failed to copy to clipboard: {e}")


if __name__ == "__main__":
    main()
