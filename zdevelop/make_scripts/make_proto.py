import pathlib


def fix_import_paths(python_file: pathlib.Path):
    file_text = python_file.read_text()
    file_text = file_text.replace("from stalk_proto", "from protogen.stalk_proto",)
    file_text = file_text.replace("import stalk_proto", "import protogen.stalk_proto",)
    file_text = file_text.replace("[stalk_proto", "[protogen.stalk_proto",)
    file_text = file_text.replace(" stalk_proto.", " protogen.stalk_proto.",)
    python_file.write_text(file_text)


def fix_generated_files():
    for python_file in pathlib.Path("./protogen").rglob("./**/*.py"):
        fix_import_paths(python_file)


if __name__ == "__main__":
    fix_generated_files()
