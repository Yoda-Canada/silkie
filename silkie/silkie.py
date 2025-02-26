import glob
import re
import shutil
from json.decoder import JSONDecodeError
from os import makedirs, path
from pathlib import Path

import click
import markdown
from yattag import Doc, indent

import silkie.definitions as definitions
from silkie.options import GeneratorOptions
from silkie.utils import TextColor, is_filetype_supported


@click.command()
@click.version_option("0.1.0", "-v", "--version")
@click.help_option("-h", "--help")
@click.option(
    "-i",
    "--input",
    "input_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, readable=True),
    help="Path to the input file/folder",
)
@click.option("-s", "--stylesheet", help="URL path to a stylesheet")
@click.option("-l", "--lang", help="Language of the HTML document [en-CA by default]")
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    help="Read option defaults from the specified INI file",
)
def silkie(input_path, stylesheet, lang, config):
    """Static site generator with the smoothness of silk"""
    try:
        options = GeneratorOptions(
            input_path,
            stylesheet_url=stylesheet,
            lang=lang,
            config_file_path=config,
        )
        # Clean build
        shutil.rmtree(definitions.DIST_DIRECTORY_PATH, ignore_errors=True)
        makedirs(definitions.DIST_DIRECTORY_PATH, exist_ok=True)
        # Generate static file(s)
        if path.isfile(options.input_path) and is_filetype_supported(
            options.input_path
        ):
            options.load_metadata()
            generate_static_file(options)
        if path.isdir(options.input_path):
            dir_path = options.input_path
            for extension in definitions.SUPORTED_FILE_EXTENSIONS:
                for filepath in glob.glob(path.join(dir_path, "*" + extension)):
                    options.input_path = filepath
                    options.load_metadata()
                    generate_static_file(options)
    except FileNotFoundError as file_error:
        click.echo(f"{TextColor.FAIL}\u2715 {str(file_error)}{TextColor.ENDC}")
    except JSONDecodeError as json_error:
        click.echo(f"{TextColor.FAIL}\u2715 {str(json_error)}{TextColor.ENDC}")
    except OSError as os_error:
        click.echo(f"{TextColor.FAIL}\u2715 {str(os_error)}{TextColor.ENDC}")


def get_title(file_path: str) -> str:
    """
    Get the title of the file based on its position in the file.
    If there is a title, it will be the first line followed by two blank lines.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        # regEx matches everything except line terminators from the beginning
        # and 3 line-feed characters (2 new lines)
        title = re.compile(r"^.+(\n\n\n)").search(f.read())
        if title is not None:
            return title.group(0).strip()
    return ""


def get_html_head(doc: Doc, options: GeneratorOptions) -> None:
    """Get the metadata of the file and append them to the HTML document"""
    with doc.tag("head"):
        doc.stag("meta", charset="utf-8")
        doc.stag(
            "meta",
            name="viewport",
            content="width=device-width, initial-scale=1",
        )
        doc.stag("meta", name="description", content=options.description)
        doc.stag("meta", property="og:description", content=options.description)
        with doc.tag("title"):
            doc.text(options.title)
        if options.stylesheet_url is not None:
            doc.stag("link", rel="stylesheet", href=options.stylesheet_url)


def parse_text(line, options: GeneratorOptions) -> None:
    """Get all paragraphs from text file and append them to the HTML document"""
    options.title = get_title(options.input_path)
    paragraphs = options.content[len(options.title) + 1 : -1].strip().split("\n\n")

    if options.title:
        line("h1", options.title)

    for paragraph_text in paragraphs:
        line("p", paragraph_text)


def parse_markdown(doc: Doc, content: str) -> None:
    """Convert Markdown to HTML and append it to the HTML document"""
    doc.asis(markdown.markdown(content.strip()))


def get_html(options: GeneratorOptions) -> str:
    doc, tag, text, line = Doc().ttl()

    doc.asis("<!DOCTYPE html>")
    with tag("html"):
        doc.attr(lang=options.lang)
        get_html_head(doc, options)
        with tag("body"):
            file_extension = Path(options.input_path).suffix
            if file_extension == ".txt":
                parse_text(line, options)
            elif file_extension == ".md":
                parse_markdown(doc, options.content)

    return indent(doc.getvalue())


def write_static_file(
    content: str, destination: Path, options: GeneratorOptions
) -> None:
    """Write the static file to the destination path"""
    with destination.open("w+", encoding="utf-8") as static_file:
        static_file.write(content)
        click.echo(
            f"{TextColor.OKGREEN}{TextColor.BOLD}\u2713 Success: "
            f"Static file for '{options.slug}' is generated in dist/{TextColor.ENDC}"
        )


def build_folder_structure(options: GeneratorOptions) -> Path:
    """
    Set up folder structure of the build folder `dist/` based on
    the value of `slug` inside `GeneratorOptions`

    :returns: the file path to the generated file
    """
    route = Path(definitions.DIST_DIRECTORY_PATH).joinpath(Path(options.slug + ".html"))

    if route.exists():
        raise FileExistsError(
            "warn: Duplicate routes found!\n"
            f"{options.slug} is already taken by another document"
        )
    dir_path = route.parent
    dir_path.mkdir(parents=True, exist_ok=True)

    return route


def generate_static_file(options: GeneratorOptions) -> None:
    """
    Parse a text file and generate a single HTML file from its content.
    The generated files should be found inside `dist/` directory
    """
    html = get_html(options)
    file_path = build_folder_structure(options)
    write_static_file(content=html, destination=file_path, options=options)
