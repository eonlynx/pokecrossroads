#!/usr/bin/env python3
"""
Final script to create a comprehensive report with proper SYSTEM_FLAGS evaluation
"""

import ast
import operator
import os
import re
import sys
from collections import defaultdict

# Safe arithmetic evaluator: parses an integer expression (+ - *, parentheses)
# via the `ast` module and computes it without ever executing arbitrary code.
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Mod: operator.mod,  # used by alignment exprs, e.g. (8 - X % 8)
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def _safe_arith(node):
    if isinstance(node, ast.Expression):
        return _safe_arith(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_arith(node.left), _safe_arith(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_arith(node.operand))
    raise ValueError("unsupported expression")

def evaluate_expression(expr: str, constants: dict) -> int:
    """Evaluate a flag expression over known constants.

    Handles plain hex/decimal values and arbitrary arithmetic over already
    resolved constants, e.g. `(TRAINER_FLAGS_START + MAX_TRAINERS_COUNT - 1)`.
    Returns None if any identifier is still unknown.
    """
    expr = expr.strip()
    if not expr:
        return None

    # Plain literals.
    if re.fullmatch(r'0[xX][0-9A-Fa-f]+', expr):
        return int(expr, 16)
    if re.fullmatch(r'-?\d+', expr):
        return int(expr)

    # Substitute every identifier with its resolved value, then evaluate the
    # remaining pure-arithmetic string. Bail out if a name is not yet known.
    tokens = re.findall(r'[A-Za-z_]\w*|0[xX][0-9A-Fa-f]+|\d+|[()+\-*%]', expr)
    rebuilt = []
    for tok in tokens:
        if re.fullmatch(r'[A-Za-z_]\w*', tok):
            if tok not in constants:
                return None
            rebuilt.append(str(constants[tok]))
        else:
            rebuilt.append(tok)
    safe = ''.join(rebuilt)
    if not re.fullmatch(r'[0-9xXa-fA-F()+\-*% ]+', safe):
        return None
    try:
        return _safe_arith(ast.parse(safe, mode='eval'))
    except Exception:
        return None

def load_external_constants(flags_filepath: str) -> dict:
    """Load constants defined in sibling headers that flags.h depends on.

    TRAINER_FLAGS_END is `TRAINER_FLAGS_START + MAX_TRAINERS_COUNT - 1`, but
    MAX_TRAINERS_COUNT lives in opponents.h. Without it the trainer-flag range
    cannot be computed and collisions go undetected.
    """
    extra = {}
    base_dir = os.path.dirname(os.path.abspath(flags_filepath))
    opponents = os.path.join(base_dir, 'opponents.h')
    if os.path.exists(opponents):
        with open(opponents, 'r') as f:
            for line in f:
                m = re.match(r'^\s*#define\s+(MAX_TRAINERS_COUNT\w*)\s+(\d+)', line)
                if m:
                    extra[m.group(1)] = int(m.group(2))
    return extra

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
    
    # Seed constants that live in sibling headers (notably MAX_TRAINERS_COUNT,
    # which drives TRAINER_FLAGS_END). Without these the trainer-flag range is
    # computed from a stale inline comment and collisions go undetected.
    constants.update(load_external_constants(filepath))

    # Second pass: evaluate expressions FIRST, so computed values win over any
    # stale inline comment. e.g. TRAINER_FLAGS_END is
    # (TRAINER_FLAGS_START + MAX_TRAINERS_COUNT - 1), whose real value (0xB55)
    # differs from the `// 0x85F` comment left over from vanilla Emerald.
    max_iterations = 10
    for _ in range(max_iterations):
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

    # Last-resort fallback: for anything STILL unresolved (e.g. a missing
    # external constant), trust an inline comment like `// 0x860`.
    for line in lines:
        match = re.match(flag_pattern, line)
        if match:
            name = match.group(1)
            value = match.group(2).strip()
            comment_match = re.search(r'//\s*(0x[0-9A-Fa-f]+)', value)
            if comment_match and name not in constants:
                constants[name] = int(comment_match.group(1), 16)
    
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

    # Detect flags that alias the (expanded) trainer-defeated flag range.
    # Trainer flags are NOT individual #defines: every defeated trainer runs
    # FlagSet(TRAINER_FLAGS_START + trainerId). So any *other* flag whose value
    # lands inside [TRAINER_FLAGS_START, TRAINER_FLAGS_END] shares a save bit
    # with a trainer and gets silently corrupted (the item never appears, the
    # event thinks it already happened). The duplicate-value check above cannot
    # see this because the trainer side of the collision is generated, not a
    # literal #define.
    trainer_start = constants.get('TRAINER_FLAGS_START')
    trainer_end = constants.get('TRAINER_FLAGS_END')
    trainer_collisions = []
    if trainer_start is not None and trainer_end is not None:
        for flag_name, flag_info in sorted(flags.items(), key=lambda x: x[1]['actual_value']):
            v = flag_info['actual_value']
            if trainer_start <= v <= trainer_end:
                trainer_collisions.append((flag_name, v))

    print(f"Found {len(trainer_collisions)} flags colliding with the trainer-flag range")
    
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

        # Add trainer-range collision section.
        f.write("TRAINER-FLAG RANGE COLLISIONS:\n")
        f.write("-" * 60 + "\n")
        if trainer_start is not None and trainer_end is not None:
            f.write(f"Trainer-defeated flags occupy 0x{trainer_start:X}..0x{trainer_end:X} "
                    f"(FlagSet(TRAINER_FLAGS_START + trainerId) per defeated trainer).\n")
            if trainer_collisions:
                f.write(f"⚠️  {len(trainer_collisions)} flag(s) alias this range and WILL be "
                        f"corrupted by trainer battles:\n\n")
                for flag_name, v in trainer_collisions:
                    f.write(f"   - {flag_name} = 0x{v:04X}  (== trainer id {v - trainer_start})\n")
            else:
                f.write("✅ No flags collide with the trainer-flag range.\n")
        else:
            f.write("(Could not resolve TRAINER_FLAGS_START/END — check opponents.h.)\n")

        f.write("\n")

        # Add statistics
        f.write("STATISTICS:\n")
        f.write("-" * 60 + "\n")
        f.write(f"Total flags processed: {len(flags)}\n")
        f.write(f"Unique memory locations: {len(used_values)}\n")
        f.write(f"Conflicts: {len(conflicts)}\n")
        f.write(f"Trainer-range collisions: {len(trainer_collisions)}\n")
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
    print(f"Trainer-range collisions: {len(trainer_collisions)}")
    if trainer_start is not None and trainer_end is not None:
        print(f"Trainer-flag range: 0x{trainer_start:X}..0x{trainer_end:X}")
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
    
    if conflicts or trainer_collisions:
        if conflicts:
            print(f"\n⚠️  WARNING: {len(conflicts)} duplicate-value conflicts detected!")
        if trainer_collisions:
            print(f"⚠️  WARNING: {len(trainer_collisions)} flags collide with the trainer-flag "
                  f"range and will be corrupted by trainer battles!")
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
