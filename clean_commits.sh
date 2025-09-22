#!/bin/bash

# Clean up commit messages to be shorter and cleaner

# Array of commit hashes and their new messages
declare -A new_messages=(
    ["5e5feba"]="docs: update realtime service documentation"
    ["a19d231"]="feat: restore advanced realtime service with backpressure management"
    ["d168917"]="fix: clean up duplicate realtime service folders"
    ["d5fd729"]="fix: clean up duplicate router service folders"
    ["7a8d342"]="fix: consolidate Docker files organization"
    ["9108dd9"]="fix: consolidate Kubernetes directories"
)

# Use filter-branch to rewrite commit messages
git filter-branch --msg-filter '
    commit_hash=$(git rev-parse --short HEAD)
    case $commit_hash in
        5e5feba*) echo "docs: update realtime service documentation" ;;
        a19d231*) echo "feat: restore advanced realtime service with backpressure management" ;;
        d168917*) echo "fix: clean up duplicate realtime service folders" ;;
        d5fd729*) echo "fix: clean up duplicate router service folders" ;;
        7a8d342*) echo "fix: consolidate Docker files organization" ;;
        9108dd9*) echo "fix: consolidate Kubernetes directories" ;;
        *) cat ;;
    esac
' HEAD~6..HEAD
