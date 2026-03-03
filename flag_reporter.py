#!/usr/bin/env python3
"""
Final script to create a comprehensive report with proper SYSTEM_FLAGS evaluation
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
        # Remove parentheses and split
        expr = expr.replace('(', '').replace(')', '').strip()
        parts = [p.strip() for p in expr.split('+')]
        
        if len(parts) == 2:
            # Find the constant value
            constant_name = parts[0]
            if constant_name in constants:
                constant_value = constants[constant_name]
                
                # Parse the offset
                offset_str = parts[1]
                try:
                    if offset_str.startswith('0x') or offset_str.startswith('0X'):
                        offset = int(offset_str, 16)
                    else:
                        offset = int(offset_str)
                    
                    return constant_value + offset
                except ValueError:
                    # If offset is not a number, skip this expression
                    pass
    
    return None

def parse_flags_file(filepath: str):
    """Parse the flags file and extract all flag definitions with their actual values"""
    
    with open(filepath, 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    # First pass: collect all constant definitions and comment values
    constants = {}
    flag_pattern = r'^\s*#define\s+(\w+)\s+([^/\n]+)'
    
    for line in lines:
        match = re.match(flag_pattern, line)
        if match:
            name = match.group(1)
            value = match.group(2).strip()
            
            # Skip if it's a comment
            if value.startswith('//'):
                continue
            
            # Try to parse as simple value first
            try:
                if value.startswith('0x') or value.startswith('0X'):
                    constants[name] = int(value, 16)
                else:
                    constants[name] = int(value)
            except ValueError:
                # If it's a complex expression, we'll evaluate it in the second pass
                pass
    
    # Special case: extract commented values for undefined constants
    for line in lines:
        match = re.match(flag_pattern, line)
        if match:
            name = match.group(1)
            value = match.group(2).strip()
            
            # Look for commented hex values like // 0x860
            comment_match = re.search(r'//\s*(0x[0-9A-Fa-f]+)', value)
            if comment_match and name not in constants:
                constants[name] = int(comment_match.group(1), 16)
    
    # Special handling for SYSTEM_FLAGS based on the comment
    if 'SYSTEM_FLAGS' not in constants:
        constants['SYSTEM_FLAGS'] = 0x860  # From the comment // 0x860
    
    # Special handling for TRAINER_FLAGS_END based on the comment
    if 'TRAINER_FLAGS_END' not in constants:
        constants['TRAINER_FLAGS_END'] = 0x85F  # From the comment // 0x85F
    
    # Second pass: evaluate all expressions and build constants map
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
    
    # Third pass: collect all flags with their actual values
    flags = {}
    value_to_flags = defaultdict(list)
    
    for i, line in enumerate(lines):
        match = re.match(flag_pattern, line)
        if match:
            name = match.group(1)
            value = match.group(2).strip()
            
            if value.startswith('//'):
                continue
            
            # Skip FLAGS_START and FLAGS_END definitions
            if 'FLAGS_START' in name or 'FLAGS_END' in name:
                continue
            
            # Evaluate the actual value
            actual_value = evaluate_expression(value, constants)
            
            if actual_value is not None:
                flags[name] = {
                    'raw_value': value,
                    'actual_value': actual_value,
                    'line_index': i,
                    'is_expression': '+' in value and '(' in value
                }
                value_to_flags[actual_value].append(name)
    
    return flags, value_to_flags, constants

def create_final_flag_report(filepath: str):
    """Create the final comprehensive report with proper SYSTEM_FLAGS evaluation"""
    
    print("Creating final comprehensive flag report...")
    
    flags, value_to_flags, constants = parse_flags_file(filepath)
    
    print(f"Found {len(flags)} flag definitions")
    print(f"Found {len(constants)} constants")
    
    # Find conflicts
    conflicts = []
    used_values = set()
    
    for value, flag_list in value_to_flags.items():
        if len(flag_list) > 1:
            conflicts.append((value, flag_list))
        used_values.add(value)
    
    print(f"Found {len(conflicts)} conflicts")
    
    # Create the report file
    report_file = filepath.replace('.h', '_final_report.txt')
    
    with open(report_file, 'w') as f:
        f.write("FINAL COMPREHENSIVE FLAG MEMORY ALLOCATION REPORT\n")
        f.write("=" * 60 + "\n")
        f.write(f"Generated from: {filepath}\n")
        f.write(f"Total flags: {len(flags)}\n")
        f.write(f"Total conflicts: {len(conflicts)}\n")
        f.write(f"Value range: 0x{min(used_values):X} to 0x{max(used_values):X}\n")
        f.write("\n")
        
        # Add constants section for debugging
        f.write("KEY CONSTANTS FOUND:\n")
        f.write("-" * 60 + "\n")
        important_constants = ['SYSTEM_FLAGS', 'TRAINER_FLAGS_START', 'TRAINER_FLAGS_END', 
                              'DAILY_FLAGS_START', 'SPECIAL_FLAGS_START', 'TESTING_FLAGS_START']
        for const in important_constants:
            if const in constants:
                f.write(f"{const} = 0x{constants[const]:X}\n")
        f.write("\n")
        
        # Sort flags by actual value for organized report
        sorted_flags = sorted(flags.items(), key=lambda x: x[1]['actual_value'])
        
        f.write("FLAG MEMORY ALLOCATIONS:\n")
        f.write("-" * 60 + "\n")
        f.write("Format: FLAG_NAME = 0xVALUE (raw_definition)\n")
        f.write("\n")
        
        for flag_name, flag_info in sorted_flags:
            actual_value = flag_info['actual_value']
            raw_value = flag_info['raw_value']
            
            # Format the output
            if flag_info['is_expression']:
                f.write(f"{flag_name} = 0x{actual_value:04X} ({raw_value})\n")
            else:
                f.write(f"{flag_name} = 0x{actual_value:04X}\n")
        
        f.write("\n")
        
        # Add conflicts section if any exist
        if conflicts:
            f.write("CONFLICTS DETECTED:\n")
            f.write("-" * 60 + "\n")
            
            conflicts.sort(key=lambda x: x[0])
            
            for i, (value, flag_list) in enumerate(conflicts):
                f.write(f"\n{i+1}. CONFLICT at value 0x{value:04X} ({value}):\n")
                for flag_name in flag_list:
                    flag_info = flags[flag_name]
                    f.write(f"   - {flag_name} = {flag_info['raw_value']}\n")
        else:
            f.write("CONFLICTS DETECTED:\n")
            f.write("-" * 60 + "\n")
            f.write("✅ NO CONFLICTS FOUND! All flags have unique memory locations.\n")
        
        f.write("\n")
        
        # Add statistics
        f.write("STATISTICS:\n")
        f.write("-" * 60 + "\n")
        f.write(f"Total flags processed: {len(flags)}\n")
        f.write(f"Unique memory locations: {len(used_values)}\n")
        f.write(f"Conflicts: {len(conflicts)}\n")
        f.write(f"Flags with expressions: {sum(1 for f in flags.values() if f['is_expression'])}\n")
        f.write(f"Flags with simple values: {sum(1 for f in flags.values() if not f['is_expression'])}\n")
        
        if used_values:
            f.write(f"Value range: 0x{min(used_values):X} to 0x{max(used_values):X}\n")
            f.write(f"Total memory range used: {max(used_values) - min(used_values) + 1} locations\n")
    
    print(f"Final report saved to: {report_file}")
    
    # Print summary
    print(f"\nFINAL REPORT SUMMARY:")
    print("=" * 60)
    print(f"Total flags: {len(flags)}")
    print(f"Conflicts: {len(conflicts)}")
    print(f"Value range: 0x{min(used_values):X} to 0x{max(used_values):X}")
    
    # Show some specific flags the user mentioned
    print(f"\nSPECIFIC FLAGS YOU MENTIONED:")
    print("-" * 60)
    if 'FLAG_RECEIVED_POKEDEX_FROM_BIRCH' in flags:
        info = flags['FLAG_RECEIVED_POKEDEX_FROM_BIRCH']
        print(f"FLAG_RECEIVED_POKEDEX_FROM_BIRCH = 0x{info['actual_value']:04X} ({info['raw_value']})")
    
    if 'FLAG_UNUSED_0x8E5' in flags:
        info = flags['FLAG_UNUSED_0x8E5']
        print(f"FLAG_UNUSED_0x8E5 = 0x{info['actual_value']:04X} ({info['raw_value']})")
    
    # Show some system flags
    print(f"\nSYSTEM FLAGS EXAMPLES:")
    print("-" * 60)
    system_flags = [name for name in flags.keys() if name.startswith('FLAG_SYS_')][:5]
    for flag_name in system_flags:
        info = flags[flag_name]
        print(f"{flag_name} = 0x{info['actual_value']:04X} ({info['raw_value']})")
    
    if conflicts:
        print(f"\n⚠️  WARNING: {len(conflicts)} conflicts detected!")
        print("Check the report file for details.")
        return False
    else:
        print(f"\n✅ SUCCESS: All flags have unique memory locations!")
        return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 create_final_flag_report.py <path_to_flags.h>")
        sys.exit(1)
    
    flags_file = sys.argv[1]
    success = create_final_flag_report(flags_file)
    
    if not success:
        sys.exit(1)
