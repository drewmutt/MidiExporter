#!/usr/bin/env python3
"""
Test script to verify that D#2 notes are handled correctly with negative octave shift
"""

import sys
sys.path.append('.')
from midi_transcriber import note_to_button_index, convert_to_midi_notes, format_midi_notes_as_c_array

def test_d_sharp_2():
    """Test that D#2 produces the correct negative octave shift"""
    
    print("Testing D#2 note handling...")
    print("=" * 50)
    
    # Test D#2 specifically
    button_index, octave_shift = note_to_button_index("D#2")
    print(f"D#2 -> button_index: {button_index}, octave_shift: {octave_shift}")
    
    # The lowest D# in our mapping should be D#3 (button index 10)
    # So D#2 should map to D#3 with octave_shift = 2 - 3 = -1
    
    # Let's also check what D#3 maps to for comparison
    button_index_d3, octave_shift_d3 = note_to_button_index("D#3")
    print(f"D#3 -> button_index: {button_index_d3}, octave_shift: {octave_shift_d3}")
    
    # And D#4 for completeness
    button_index_d4, octave_shift_d4 = note_to_button_index("D#4")
    print(f"D#4 -> button_index: {button_index_d4}, octave_shift: {octave_shift_d4}")
    
    print("\nExpected results:")
    print("D#2 should map to D#3's button (10) with octave_shift = -1")
    print("D#3 should map to button 10 with octave_shift = 0")
    print("D#4 should map to button 22 with octave_shift = 0")
    
    # Test with note events
    print("\n" + "="*50)
    print("Testing with note events...")
    
    # Create test note events with D#2
    note_events = [
        ("D#2", 1000, "ON"),
        ("D#2", 2000, "OFF"),
        ("D#3", 3000, "ON"),
        ("D#3", 4000, "OFF")
    ]
    
    print("\nOriginal note events:")
    for event in note_events:
        print(f"  {event}")
    
    # Convert to MidiNote structs
    midi_notes = convert_to_midi_notes(note_events)
    
    print("\nMidiNote struct format:")
    print("Format: {index, noteButtonIndex, octaveShift, timeMSec, isOn}")
    for note in midi_notes:
        print(f"  {{{note.index}, {note.noteButtonIndex}, {note.octaveShift}, {note.timeMSec}, {note.isOn}}}")
    
    # Print C-style array
    print(f"\nC-style array initialization:")
    c_array_format = format_midi_notes_as_c_array(midi_notes)
    print(c_array_format)
    
    print("\n" + "="*50)
    print("Verification:")
    print("D#2 should have octave_shift = -1")
    print("D#3 should have octave_shift = 0")
    
    # Check the results
    d2_note = midi_notes[0]  # First note should be D#2
    d3_note = midi_notes[2]  # Third note should be D#3
    
    if d2_note.octaveShift == -1:
        print("✓ D#2 correctly has octave_shift = -1")
    else:
        print(f"✗ D#2 has octave_shift = {d2_note.octaveShift}, expected -1")
    
    if d3_note.octaveShift == 0:
        print("✓ D#3 correctly has octave_shift = 0")
    else:
        print(f"✗ D#3 has octave_shift = {d3_note.octaveShift}, expected 0")

if __name__ == "__main__":
    test_d_sharp_2()