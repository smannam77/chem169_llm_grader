#!/bin/bash
# Sync route instructions from portal repo to grader repo
# Portal is source of truth

PORTAL_ROUTES="/Users/ajinich/Documents/repos/climbing-gym-app/content/routes"
GRADER_ASSIGNMENTS="/Users/ajinich/Documents/repos/chem169_llm_grader/assignments"

echo "Syncing instructions from portal → grader..."

for portal_file in "$PORTAL_ROUTES"/R[0-9]*.md; do
    # Extract route number (R001, R012, etc.)
    filename=$(basename "$portal_file")
    route_num=$(echo "$filename" | grep -oE '^R[0-9]+')

    # Convert R001 → RID_001
    rid=$(echo "$route_num" | sed 's/R/RID_/' | sed 's/RID_\([0-9]\)$/RID_00\1/' | sed 's/RID_\([0-9][0-9]\)$/RID_0\1/')

    # Target path
    target_dir="$GRADER_ASSIGNMENTS/$rid"
    target_file="$target_dir/instructions.md"

    # Create directory if needed
    mkdir -p "$target_dir"

    # Copy file
    if [ -f "$portal_file" ]; then
        cp "$portal_file" "$target_file"
        echo "  ✓ $filename → $rid/instructions.md"
    fi
done

echo ""
echo "Done! Synced $(ls "$PORTAL_ROUTES"/R[0-9]*.md 2>/dev/null | wc -l | tr -d ' ') routes."
