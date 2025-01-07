import os


def generate_tree_md(path, indent=0):
    """Recursively generate the directory structure in Markdown format, excluding __pycache__."""
    md_lines = []
    items = os.listdir(path)  # Sort items alphabetically
    for item in items:
        if item == "__pycache__":  # Skip __pycache__ directories
            continue
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            # Add folder with proper indentation
            md_lines.append(f"{' ' * indent}- **{item}**/")
            md_lines.extend(generate_tree_md(item_path, indent + 2))
        else:
            # Add file with proper indentation
            md_lines.append(f"{' ' * indent}- {item}")
    return md_lines


def save_tree_to_md(root_path, output_file):
    """Generate project structure and save to a markdown file."""
    tree_md = generate_tree_md(root_path)
    with open(output_file, "w") as f:
        f.write("# Project Structure\n\n")
        f.write("\n".join(tree_md))
    print(f"Project structure saved to {output_file}")


# Define your project path
project_path = "../src/"  # Current directory or specify the path
absolute_src_path = os.path.abspath(project_path)
print(f"Project path: {absolute_src_path}")
output_file = "project_structure.md"

save_tree_to_md(project_path, output_file)
