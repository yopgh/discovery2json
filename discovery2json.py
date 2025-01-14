#!/usr/bin/env python3
import os
import json
import time
import argparse
import re

def resolve_schema(schema_name, schemas, seen_schemas=None, max_depth=10, max_branches=10, start_depth=1, blacklisted_schemas=None, include_docs=False):
    if seen_schemas is None:
        seen_schemas = []

    current_depth = len(seen_schemas)

    if blacklisted_schemas is None:
        blacklisted_schemas = []

    if schema_name in blacklisted_schemas:
        return "(hidden: blacklisted)"

    if current_depth >= start_depth:
        if current_depth >= max_depth:
            schema = schemas.get(schema_name, {})
            num_properties = len(schema.get("properties", {}))
            return f"({num_properties} properties hidden: max recursion exceeded)"

        if schema_name in seen_schemas:
            return "(recursion stopped)"

        if len(schemas.get(schema_name, {}).get("properties", {})) > max_branches:
            return f"({len(schemas[schema_name]['properties'])} properties hidden: max branches exceeded)"

    seen_schemas.append(schema_name)

    resolved_properties = {}
    schema = schemas.get(schema_name, {})
    properties = schema.get("properties", {})
    description = schema.get("description", "").strip()

    if include_docs and description:
        resolved_properties["__DOCS"] = description

    for key, value in properties.items():
        if "$ref" in value:
            resolved_properties[key] = resolve_schema(
                value["$ref"], schemas, seen_schemas, max_depth, max_branches, start_depth, blacklisted_schemas, include_docs
            )
        elif value.get("type") == "array":
            item_type = value.get("items", {}).get("type", "unknown")
            item_schema = resolve_schema(
                value.get("items", {}).get("$ref", None), schemas, seen_schemas, max_depth, max_branches, start_depth, blacklisted_schemas, include_docs
            ) if "$ref" in value.get("items", {}) else f"<{item_type}>"
            if include_docs and value.get("description", "").strip():
                resolved_properties[key] = [f"(DOCS: {value['description']})", item_schema]
            else:
                resolved_properties[key] = [item_schema]
        elif value.get("type") == "object":
            child_schema = resolve_schema(
                value.get("$ref", None), schemas, seen_schemas, max_depth, max_branches, start_depth, blacklisted_schemas, include_docs
            ) if "$ref" in value else {}
            resolved_properties[key] = child_schema
            if include_docs and value.get("description", "").strip():
                resolved_properties[key]["__DOCS"] = value["description"]
        elif "enum" in value:
            enum_values = value["enum"]
            enum_descriptions = value.get("enumDescriptions", [])
            if enum_descriptions and any(desc.strip() for desc in enum_descriptions):
                resolved_properties[key] = "|".join(
                    f"{val}: {desc.strip()}" if desc.strip() else val
                    for val, desc in zip(enum_values, enum_descriptions)
                )
                resolved_properties[key] = f"<{resolved_properties[key]}>"
            else:
                resolved_properties[key] = f"<{"|".join(enum_values)}>"
        else:
            type_str = f"<{value.get('type', 'unknown')}>"
            if include_docs and value.get("description", "").strip():
                type_str = f"<{value.get('type', 'unknown')}: {value['description']}>"
            resolved_properties[key] = type_str

    seen_schemas.pop()
    return resolved_properties

def write_file_with_stats(output_dir, file_path, resolve_function):
    rel_path = os.path.relpath(file_path, start=output_dir)
    print(f"[*] {rel_path}...", end="", flush=True)

    start_time = time.time()
    content = resolve_function()

    with open(file_path, 'w') as f:
        json.dump(content, f, indent=4)

    elapsed_time = time.time() - start_time
    file_size = len(json.dumps(content, indent=4))
    print(f"\r[*] {elapsed_time:.2f}s {file_size}B {rel_path}")

def extract_methods_and_paths(resource, output_dir):
    directories_to_create = []

    if "methods" in resource:
        for method_name, method_data in resource["methods"].items():
            if "path" in method_data:
                method_dir = os.path.join(output_dir, method_data["path"].lstrip("/").replace("/", os.sep), method_data.get("httpMethod", "UNKNOWN").upper())
                directories_to_create.append((method_dir, method_data))

    if "resources" in resource:
        for subresource in resource["resources"].values():
            directories_to_create.extend(extract_methods_and_paths(subresource, output_dir))

    return directories_to_create

def analyze_discovery_doc(discovery_doc, output_dir, regex):
    directories_to_create = []

    for resource in discovery_doc.get("resources", {}).values():
        directories_to_create.extend(extract_methods_and_paths(resource, output_dir))

    filtered_directories = [entry for entry in directories_to_create if re.search(regex, entry[0])]

    return filtered_directories

def generate_json_files(discovery_doc_path, output_dir, request_params, response_params, blacklisted_schemas, regex, include_docs):
    with open(discovery_doc_path, 'r') as f:
        discovery_doc = json.load(f)

    directories_to_create = analyze_discovery_doc(discovery_doc, output_dir, regex)

    for method_dir, method_data in directories_to_create:
        os.makedirs(method_dir, exist_ok=True)

        schemas = discovery_doc.get("schemas", {})

        for io_type in ["request", "response"]:
            file_path = os.path.join(method_dir, f"{io_type}.json")
            write_file_with_stats(
                output_dir,
                file_path,
                lambda: resolve_schema(
                    method_data.get(io_type, {}).get("$ref", ""),
                    schemas,
                    **(request_params if io_type == "request" else response_params),
                    blacklisted_schemas=blacklisted_schemas,
                    include_docs=include_docs
                ) if io_type in method_data else {}
            )

    print(f"Files generated in directory: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate JSON files for API request and response schemas.")
    parser.add_argument("discovery_doc", type=str, help="Path to the discovery JSON file.")
    parser.add_argument("output_dir", type=str, help="Path to the output directory.")
    parser.add_argument("--request-max-depth", type=int, default=100, help="Maximum recursion depth for requests.")
    parser.add_argument("--request-start-depth", type=int, default=1, help="Start depth for applying recursion checks in requests.")
    parser.add_argument("--request-max-branches", type=int, default=10, help="Maximum branches to resolve for requests.")
    parser.add_argument("--response-max-depth", type=int, default=100, help="Maximum recursion depth for responses.")
    parser.add_argument("--response-start-depth", type=int, default=1, help="Start depth for applying recursion checks in responses.")
    parser.add_argument("--response-max-branches", type=int, default=10, help="Maximum branches to resolve for responses.")
    parser.add_argument("--regex", type=str, default="^.*$", help="Regex pattern to match any part of method directories for processing.")
    parser.add_argument("--blacklisted-schemas", type=str, default="YoutubeApiInnertubeInnerTubeContext,YoutubeApiInnertubeResponseContext", help="Comma-separated list of blacklisted schemas.")
    parser.add_argument("--docs", action="store_true", help="Include documentation strings in the output JSON files.")

    args = parser.parse_args()

    request_params = {
        "max_depth": args.request_max_depth,
        "start_depth": args.request_start_depth,
        "max_branches": args.request_max_branches
    }

    response_params = {
        "max_depth": args.response_max_depth,
        "start_depth": args.response_start_depth,
        "max_branches": args.response_max_branches
    }

    blacklisted_schemas = args.blacklisted_schemas.split(",")

    generate_json_files(args.discovery_doc, args.output_dir, request_params, response_params, blacklisted_schemas, args.regex, args.docs)
