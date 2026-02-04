#!/usr/bin/env python3
"""
Test script to verify the solution works with the example from the issue description
"""

from midi_transcriber import note_to_button_index, convert_to_midi_notes, format_midi_notes_as_c_array

# Test with the example from the issue description
# The issue mentioned: MidiNote song[MAX_NOTES] = {{0, 2, 0, 2000, true}, {1, 4, 0, 2200, true}};
# Let's figure out what notes would produce this output

print("Testing with issue description example:")
print("=" * 60)

# From the mapping, button index 2 is G2, button index 4 is A3
# Let's test these specific mappings
test_cases = [
    ("G2", 2000, "ON"),   # Should map to button 2, shift 0
    ("A3", 2200, "ON"),   # Should map to button 4, shift 0
]

print("Expected from issue description:")
print("{{0, 2, 0, 2000, true}, {1, 4, 0, 2200, true}}")
print()

print("Our implementation:")
midi_notes = convert_to_midi_notes(test_cases)

for note in midi_notes:
    print(f"{{{note.index}, {note.noteButtonIndex}, {note.octaveShift}, {note.timeMSec}, {'true' if note.isOn else 'false'}}}")

print()
print("C-style array format:")
c_array = format_midi_notes_as_c_array(midi_notes)
print(c_array)

print()
print("Verification of button mappings from the provided map:")
print("-" * 60)

# Show the mapping for reference
button_mappings = [
    (0, "F2"), (1, "F#2"), (2, "G2"), (3, "G#2"), (4, "A3"), (5, "A#3"), 
    (6, "B3"), (7, "C3"), (8, "C#3"), (9, "D3"), (10, "D#3"), (11, "E3"),
    (12, "F3"), (13, "F#3"), (14, "G3"), (15, "G#3"), (16, "A4"), (17, "A#4"),
    (18, "B4"), (19, "C4"), (20, "C#4"), (21, "D4"), (22, "D#4"), (23, "E4"),
    (24, "F4"), (25, "F#4"), (26, "G4")
]

print("Button Index -> Note mapping:")
for idx, note in button_mappings[:10]:  # Show first 10 for clarity
    print(f"  {idx:2d} -> {note}")

print("  ...")
print(f"  {button_mappings[-1][0]:2d} -> {button_mappings[-1][1]}")

print()
print("Confirming our test cases:")
print(f"  G2 -> Button {note_to_button_index('G2')[0]}, Shift {note_to_button_index('G2')[1]}")
print(f"  A3 -> Button {note_to_button_index('A3')[0]}, Shift {note_to_button_index('A3')[1]}")