# Improved Resource Prospecting - reconstruct the CSV from the generated decisions txt
import csv
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DECISIONS_DIR = os.path.join(SCRIPT_DIR, '..', 'common', 'decisions')

def extract_decisions(text):
    decisions = []
    # Match active decisions defined at the first level of indentation (1 tab)
    # This automatically ignores commented-out decisions (#) and deeply nested blocks
    for m in re.finditer(r'\n\t([A-Za-z0-9_]+)\s*=\s*\{', text):
        dec_id = m.group(1)
        start_idx = m.end() - 1  # Index of the opening brace '{'
        
        # Safe curly brace counting to grab the full block correctly
        brace_count = 0
        end_idx = -1
        for i in range(start_idx, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
                    
        if end_idx != -1:
            body = text[m.start():end_idx]
            decisions.append((dec_id, body))
    return decisions

def import_decisions():
    input_file = os.path.join(DECISIONS_DIR, 'IRP.resource_prospecting.txt')
    csv_file = os.path.join(SCRIPT_DIR, 'IRP.resource_prospecting.csv')

    # Flexible path fallback if running directly in the same directory
    if not os.path.exists(input_file):
        input_file = os.path.join(SCRIPT_DIR, 'IRP.resource_prospecting.txt')
        if not os.path.exists(input_file):
            print(f"Error: IRP.resource_prospecting.txt not found.")
            return

    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    rows = []
    groups = {}
    
    decisions = extract_decisions(text)
    print(f"Found {len(decisions)} active decision blocks. Processing...")

    for dec_id, body in decisions:
        # 1. Extract State ID (Check scopes, targets, or fallback to the top comment)
        state_id = ""
        state_match = re.search(r'\b(?:state|owns_state|controls_state)\s*=\s*(\d+)', body)
        if state_match:
            state_id = state_match.group(1)
        else:
            first_line = body.split('\n')[0]
            comment_match = re.search(r'#\s*(\d+)', first_line)
            if comment_match:
                state_id = comment_match.group(1)
            else:
                any_state_num = re.search(r'\b(\d+)\s*=\s*\{', body)
                if any_state_num:
                    state_id = any_state_num.group(1)

        # 2. Extract Resource Type (Check icon definition or type within add_resource)
        res_type = ""
        res_match = re.search(r'\bicon\s*=\s*([A-Za-z0-9_]+)', body)
        if not res_match:
            res_match = re.search(r'\btype\s*=\s*([A-Za-z0-9_]+)', body)
        if res_match:
            res_type = res_match.group(1)

        # 3. Extract Resource Amount from multi-line add_resource block
        amount = ""
        amount_match = re.search(r'add_resource\s*=\s*\{[^}]*amount\s*=\s*(\d+)', body, re.DOTALL)
        if not amount_match:
            add_res_idx = body.find('add_resource')
            if add_res_idx != -1:
                amount_match = re.search(r'amount\s*=\s*(\d+)', body[add_res_idx:])
        if amount_match:
            amount = amount_match.group(1)

        # 4. Extract Required Tech (if present)
        tech = ""
        tech_match = re.search(r'\bhas_tech\s*=\s*([A-Za-z0-9_]+)', body)
        if tech_match:
            tech = tech_match.group(1)

        # 5. Determine Tier (Checks decision suffix or state flag tier numbers)
        tier = 1
        id_tier_match = re.search(r'_(\d+)$', dec_id)
        if id_tier_match:
            tier = int(id_tier_match.group(1))
        else:
            flag_match = re.search(r'set_state_flag\s*=\s*(?:\{\s*flag\s*=\s*)?([A-Za-z0-9_]+)', body)
            if flag_match:
                flag_name = flag_match.group(1)
                flag_tier_match = re.search(r'_(\d+)$', flag_name)
                if flag_tier_match:
                    tier = int(flag_tier_match.group(1))

        row = {
            'State_ID': state_id,
            'Resource_Type': res_type,
            'Resource_Amount': amount,
            'Required_Tech': tech,
            'Decision_ID': dec_id,
            'Required_Decision_ID': '',
        }
        rows.append(row)
        
        if state_id and res_type:
            groups.setdefault((state_id, res_type), {})[tier] = row

    # Automatically map higher tiers to their preceding decision tier
    for group in groups.values():
        for tier, row in group.items():
            if tier > 1 and (tier - 1) in group:
                row['Required_Decision_ID'] = group[tier - 1]['Decision_ID']

    # Output to CSV file
    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['State_ID', 'Resource_Type', 'Resource_Amount', 'Required_Tech', 'Decision_ID', 'Required_Decision_ID'])
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Successfully generated CSV with {len(rows)} entries at: {csv_file}")

if __name__ == '__main__':
    import_decisions()
