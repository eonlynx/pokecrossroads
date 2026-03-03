#!/usr/bin/env python3
"""
Single comprehensive script to fix ALL flag conflicts from backup
"""

import re
import sys
from collections import defaultdict

def evaluate_expression(expr: str, constants: dict) -> int:
    """Evaluate a flag expression like (SYSTEM_FLAGS + 0x85)"""
    expr = expr.strip()
    
    # Handle simple hex/decimal values
    if expr.startswith('0x') or expr.startswith('0X'):
        return int(expr, 16)
    try:
        return int(expr)
    except ValueError:
        pass
    
    # Handle expressions like (CONSTANT + offset)
    if '+' in expr and '(' in expr and ')' in expr:
        expr = expr.replace('(', '').replace(')', '').strip()
        parts = [p.strip() for p in expr.split('+')]
        
        if len(parts) == 2:
            constant_name = parts[0]
            if constant_name in constants:
                constant_value = constants[constant_name]
                offset_str = parts[1]
                try:
                    if offset_str.startswith('0x') or offset_str.startswith('0X'):
                        offset = int(offset_str, 16)
                    else:
                        offset = int(offset_str)
                    return constant_value + offset
                except ValueError:
                    pass
    
    return None

def parse_flags_file(filepath: str):
    """Parse the flags file and extract all flag definitions with their actual values"""
    
    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    # First pass: collect all constants
    constants = {}
    flag_pattern = r'^\s*#define\s+(\w+)\s+([^/\n]+)'
    
    for line in lines:
        match = re.match(flag_pattern, line)
        if match:
            name = match.group(1)
            value = match.group(2).strip()
            
            if value.startswith('//'):
                continue
            
            try:
                if value.startswith('0x') or value.startswith('0X'):
                    constants[name] = int(value, 16)
                else:
                    constants[name] = int(value)
            except ValueError:
                pass
    
    # Set known constants
    if 'SYSTEM_FLAGS' not in constants:
        constants['SYSTEM_FLAGS'] = 0x860
    if 'TRAINER_FLAGS_END' not in constants:
        constants['TRAINER_FLAGS_END'] = 0x85F
    
    # Second pass: evaluate expressions
    max_iterations = 10
    for iteration in range(max_iterations):
        updated = False
        for line in lines:
            match = re.match(flag_pattern, line)
            if match:
                name = match.group(1)
                value = match.group(2).strip()
                
                if name not in constants and not value.startswith('//'):
                    evaluated = evaluate_expression(value, constants)
                    if evaluated is not None:
                        constants[name] = evaluated
                        updated = True
        
        if not updated:
            break
    
    # Third pass: collect all flags
    flags = {}
    value_to_flags = defaultdict(list)
    
    for i, line in enumerate(lines):
        match = re.match(flag_pattern, line)
        if match:
            name = match.group(1)
            value = match.group(2).strip()
            
            if value.startswith('//'):
                continue
            
            if 'FLAGS_START' in name or 'FLAGS_END' in name:
                continue
            
            actual_value = evaluate_expression(value, constants)
            
            if actual_value is not None:
                flags[name] = {
                    'raw_value': value,
                    'actual_value': actual_value,
                    'line_index': i,
                    'is_expression': '+' in value and '(' in value
                }
                value_to_flags[actual_value].append(name)
    
    return flags, value_to_flags, constants, lines

def fix_all_flag_conflicts_comprehensive(filepath: str):
    """Comprehensive fix for ALL flag conflicts using optimal memory allocation"""
    
    print("=== COMPREHENSIVE FLAG CONFLICT FIX ===")
    print("Parsing flags file...")
    flags, value_to_flags, constants, lines = parse_flags_file(filepath)
    
    # Find all used values
    used_values = set()
    for flag_info in flags.values():
        used_values.add(flag_info['actual_value'])
    
    # Find duplicates
    duplicates = []
    for value, flag_list in value_to_flags.items():
        if len(flag_list) > 1:
            duplicates.append((value, flag_list))
    
    print(f"Found {len(duplicates)} duplicate values")
    
    if not duplicates:
        print("✅ No duplicates found!")
        return True
    
    # Find available slots in optimal ranges
    non_hidden_slots = []
    hidden_slots = []
    overflow_slots = []
    
    # Priority 1: Lowest possible range for non-hidden flags (0x1 to 0x1F3)
    for value in range(0x1, 0x1F4):
        if value not in used_values:
            non_hidden_slots.append(value)
    
    # Priority 2: Hidden flags range (0x1F4 to 0x800)
    for value in range(0x1F4, 0x801):
        if value not in used_values:
            hidden_slots.append(value)
    
    # Priority 3: Overflow range for remaining non-hidden flags (0x801 to 0xFFF)
    for value in range(0x801, 0x1000):
        if value not in used_values:
            overflow_slots.append(value)
    
    print(f"Available non-hidden slots (0x1-0x1F3): {len(non_hidden_slots)}")
    print(f"Available hidden slots (0x1F4-0x800): {len(hidden_slots)}")
    print(f"Available overflow slots (0x801-0xFFF): {len(overflow_slots)}")
    
    # Create backup
    backup_file = filepath.replace('.h', '_before_comprehensive_fix.h')
    with open(backup_file, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Backup created: {backup_file}")
    
    # Fix duplicates with priority system
    changes_made = 0
    non_hidden_index = 0
    hidden_index = 0
    overflow_index = 0
    
    # Sort duplicates by value (lower values first)
    duplicates.sort(key=lambda x: x[0])
    
    for value, flag_list in duplicates:
        print(f"\nFixing conflict at 0x{value:X} with {len(flag_list)} flags:")
        
        # Show all flags in this conflict
        for flag_name in flag_list:
            flag_info = flags[flag_name]
            print(f"  {flag_name} = {flag_info['raw_value']}")
        
        # Sort flags by priority (keep important flags, move others)
        flag_list.sort(key=lambda x: get_flag_priority(x))
        
        # Keep the first (highest priority) flag, move the rest
        flags_to_move = flag_list[1:]
        
        for flag_name in flags_to_move:
            flag_info = flags[flag_name]
            
            # Choose appropriate slot based on flag type and availability
            new_value = None
            
            if flag_name.startswith('FLAG_HIDDEN_ITEM_'):
                # Hidden flag - use hidden slots (≥ 0x1F4)
                if hidden_index < len(hidden_slots):
                    new_value = hidden_slots[hidden_index]
                    hidden_index += 1
                else:
                    print(f"  Warning: No hidden slot available for {flag_name}")
                    continue
            else:
                # Non-hidden flag - try non-hidden slots first, then overflow
                if non_hidden_index < len(non_hidden_slots):
                    new_value = non_hidden_slots[non_hidden_index]
                    non_hidden_index += 1
                elif overflow_index < len(overflow_slots):
                    new_value = overflow_slots[overflow_index]
                    overflow_index += 1
                else:
                    print(f"  Warning: No slot available for {flag_name}")
                    continue
            
            # Update the line with precise replacement
            line_index = flag_info['line_index']
            old_line = lines[line_index]
            
            # Use regex to replace only the exact value part
            import re
            # Pattern to match the exact value in #define context
            pattern = rf'(#define\s+{re.escape(flag_name)}\s+){re.escape(flag_info["raw_value"])}(\s|$)'
            replacement = rf'\g<1>0x{new_value:X}\g<2>'
            new_line = re.sub(pattern, replacement, old_line)
            
            lines[line_index] = new_line
            
            print(f"  Moved {flag_name} to 0x{new_value:X}")
            changes_made += 1
            used_values.add(new_value)
    
    # Write the updated file
    with open(filepath, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"\n=== SUMMARY ===")
    print(f"Fixed {changes_made} flag conflicts")
    print(f"Used {non_hidden_index} low-range slots (0x1-0x1F3)")
    print(f"Used {hidden_index} hidden slots (0x1F4-0x800)")
    print(f"Used {overflow_index} overflow slots (0x801-0xFFF)")
    
    # Verify the fix
    print("\nVerifying fix...")
    updated_flags, updated_value_to_flags, _, _ = parse_flags_file(filepath)
    
    remaining_duplicates = []
    for value, flag_list in updated_value_to_flags.items():
        if len(flag_list) > 1:
            remaining_duplicates.append((value, flag_list))
    
    print(f"Remaining duplicates: {len(remaining_duplicates)}")
    
    if remaining_duplicates:
        print("Remaining conflicts:")
        for value, flag_list in remaining_duplicates[:5]:
            print(f"  0x{value:X}: {', '.join(flag_list[:3])}{'...' if len(flag_list) > 3 else ''}")
        return False
    else:
        print("✅ SUCCESS: All flag conflicts resolved!")
        return True

def get_flag_priority(flag_name: str) -> int:
    """Get priority for flag assignment (lower number = higher priority to keep)"""
    
    # Highest priority: System constants and important flags
    if 'FLAGS_START' in flag_name or 'FLAGS_END' in flag_name:
        return 1
    if flag_name.startswith('FLAG_SYS_'):
        return 2
    if flag_name == 'SYSTEM_FLAGS':
        return 2
    
    # High priority: Story and important game flags
    if flag_name.startswith('FLAG_RECEIVED_') or flag_name.startswith('FLAG_GOT_'):
        return 3
    if flag_name.startswith('FLAG_DEFEATED_'):
        return 3
    if flag_name.startswith('FLAG_MET_'):
        return 3
    if flag_name.startswith('FLAG_VISITED_'):
        return 3
    
    # Medium priority: Hidden items (must be ≥ 0x1F4)
    if flag_name.startswith('FLAG_HIDDEN_ITEM_'):
        return 4
    
    # Lower priority: Hide flags (non-hidden)
    if flag_name.startswith('FLAG_HIDE_'):
        return 5
    
    # Lowest priority: All other flags
    return 6

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 fix_all_flags_comprehensive.py <path_to_flags.h>")
        print("This script will fix ALL flag conflicts from backup using optimal memory allocation")
        sys.exit(1)
    
    flags_file = sys.argv[1]
    success = fix_all_flag_conflicts_comprehensive(flags_file)
    
    if not success:
        sys.exit(1)
