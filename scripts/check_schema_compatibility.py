#!/usr/bin/env python3
"""
Schema compatibility checker for contract validation
"""

import json
import sys
from pathlib import Path


def check_schema_compatibility():
    """Check that all schemas are compatible and valid"""
    schemas_dir = Path(__file__).parent.parent / "contracts" / "schemas"
    errors = []
    
    # Check that all schema files exist and are valid JSON
    schema_files = list(schemas_dir.glob("*.json"))
    
    if not schema_files:
        errors.append("No schema files found in contracts/schemas/")
        return errors
    
    for schema_file in schema_files:
        try:
            with open(schema_file, 'r') as f:
                schema = json.load(f)
            
            # Check required fields
            if "$schema" not in schema:
                errors.append(f"{schema_file.name}: Missing $schema field")
            
            if "type" not in schema:
                errors.append(f"{schema_file.name}: Missing type field")
            
            if "properties" not in schema:
                errors.append(f"{schema_file.name}: Missing properties field")
            
            # Check that $schema is Draft 7
            if schema.get("$schema") != "http://json-schema.org/draft-07/schema#":
                errors.append(f"{schema_file.name}: Schema must use Draft 7")
            
            # Check that required fields are defined in properties
            required_fields = schema.get("required", [])
            properties = schema.get("properties", {})
            
            for field in required_fields:
                if field not in properties:
                    errors.append(f"{schema_file.name}: Required field '{field}' not defined in properties")
            
            print(f"✅ {schema_file.name}: Valid")
            
        except json.JSONDecodeError as e:
            errors.append(f"{schema_file.name}: Invalid JSON - {e}")
        except Exception as e:
            errors.append(f"{schema_file.name}: Error - {e}")
    
    return errors


def main():
    """Main function"""
    print("🔍 Checking schema compatibility...")
    
    errors = check_schema_compatibility()
    
    if errors:
        print("\n❌ Schema compatibility check failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("\n✅ All schemas are compatible!")
        sys.exit(0)


if __name__ == "__main__":
    main()
