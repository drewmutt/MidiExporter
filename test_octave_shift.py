#!/usr/bin/env python3
"""
Test script to verify octave shifting logic
"""

from midi_transcriber import note_to_button_index, convert_to_midi_notes, format_midi_notes_as_c_array

# Test cases for octave shifting
test_notes = [
    "A4",   # Direct mapping - should be button 16, shift 0
    "A5",   # One octave higher than A4 - should be button 16, shift 1
    "A6",   # Two octaves higher than A4 - should be button 16, shift 2
    "C4",   # Direct mapping - should be button 19, shift 0
    "C5",   # One octave higher than C4 - should be button 19, shift 1
    "C7",   # Three octaves higher than C4 - should be button 19, shift 3
    "F4",   # Direct mapping - should be button 24, shift 0
    "F5",   # One octave higher than F4 - should be button 24, shift 1
    "G2",   # Direct mapping - should be button 2, shift 0
    "G5",   # Higher than available G4 (button 26) - should be button 26, shift 1
    "B3",   # Direct mapping - should be button 6, shift 0
    "B5",   # Higher than available B4 (button 18) - should be button 18, shift 1
]

print("Testing octave shifting logic:")
print("=" * 60)
print("Note -> (Button Index, Octave Shift)")
print("-" * 60)

for note in test_notes:
    button_idx, octave_shift = note_to_button_index(note)
    print(f"{note:4s} -> ({button_idx:2d}, {octave_shift})")

print("\n" + "=" * 60)
print("Testing with simulated note events:")
print("=" * 60)

# Create simulated note events to test the full conversion
test_events = [
    ("A4", 1000, "ON"),
    ("C5", 1500, "ON"), 
    ("G5", 2000, "ON"),
    ("A4", 2500, "OFF"),
    ("C5", 3000, "OFF"),
    ("G5", 3500, "OFF"),
]

midi_notes = convert_to_midi_notes(test_events)
c_array = format_midi_notes_as_c_array(midi_notes)

print("Original events:")
for event in test_events:
    print(f"  {event}")

print("\nConverted MidiNote structs:")
for note in midi_notes:
    print(f"  {{{note.index}, {note.noteButtonIndex}, {note.octaveShift}, {note.timeMSec}, {note.isOn}}}")

print(f"\nC-style array format:")
print(c_array)