"""
Pyinvoke tasks.py file for automating releases and admin stuff.
"""

from __future__ import annotations

import glob
import json
import os

import requests
from invoke import task
from monty.os import cd

import matgl

NEW_VER = matgl.__version__


@task
def make_doc(ctx):
    """
    This new version requires markdown builder.

        pip install sphinx-markdown-builder

    Adding the following to conf.py

        extensions = [
            'sphinx_markdown_builder'
        ]

    Build markdown files with sphinx-build command

        sphinx-build -M markdown ./ build
    """
    ctx.run("rm -rf docs/tutorials")
    ctx.run("jupyter nbconvert examples/*.ipynb --to=markdown --output-dir=docs/tutorials")
    with cd("docs"):
        ctx.run("rm matgl.*.rst", warn=True)
        ctx.run("sphinx-apidoc -P -M -d 6 -o . -f ../matgl")
        # ctx.run("rm matgl*.html", warn=True)
        # ctx.run("sphinx-build -b html . ../docs")  # HTML building.
        ctx.run("sphinx-build -M markdown . .")
        ctx.run("rm *.rst", warn=True)
        ctx.run("cp markdown/matgl*.md .")
        for fn in list(glob.glob("matgl*.md")) + list(glob.glob("tutorials/*.md")):
            with open(fn) as f:
                lines = f.readlines()
            lines = [line for line in lines if "Submodules" not in line]
            if fn == "matgl.md":
                preamble = [
                    "---",
                    "layout: default",
                    "title: API Documentation",
                    "nav_order: 5",
                    "---"
                ]
            else:
                preamble = [
                    "---",
                    "layout: default",
                    "title: " + fn,
                    "nav_exclude: true",
                    "---"
                ]
            with open(fn, "w") as f:
                f.write("\n".join(preamble) + "\n" + "".join(lines))

        ctx.run("rm -r markdown", warn=True)

        # ctx.run("mv _static static")
        # ctx.run("sed -i'.orig' -e 's/_static/static/g' matgl*.html")
        # ctx.run("rm index.html", warn=True)
        ctx.run("cp ../*.md .")
        ctx.run("mv README.md index.md")
        ctx.run("rm -rf *.orig doctrees", warn=True)

        with open("index.md") as f:
            contents = f.read()
        with open("index.md", "w") as f:
            contents = contents.replace(
                "\n### Official Documentation: [:books:][doc]",
                "{: .no_toc }\n\n## Table of contents\n{: .no_toc .text-delta }\n* TOC\n{:toc}\n")
            contents = "---\nlayout: default\ntitle: Home\nnav_order: 1\n---\n\n" + contents

            f.write(contents)


@task
def publish(ctx):
    ctx.run("rm dist/*.*", warn=True)
    ctx.run("python setup.py sdist bdist_wheel")
    ctx.run("twine upload dist/*")


@task
def release_github(ctx):
    desc = get_changelog(ctx)
    payload = {
        "tag_name": "v" + NEW_VER,
        "target_commitish": "main",
        "name": "v" + NEW_VER,
        "body": desc,
        "draft": False,
        "prerelease": False,
    }
    response = requests.post(
        "https://api.github.com/repos/materialsvirtuallab/matgl/releases",
        data=json.dumps(payload),
        headers={"Authorization": "token " + os.environ["GITHUB_RELEASES_TOKEN"]},
    )
    print(response.text)


@task
def release(ctx, notest=False):
    ctx.run("rm -r dist build matgl.egg-info", warn=True)
    if not notest:
        ctx.run("pytest tests")
    publish(ctx)
    release_github(ctx)

@task
def get_changelog(ctx):
    with open("changes.md") as f:
        contents = f.read()
        i = contents.find(f"{NEW_VER}")
        contents = contents[i+len(NEW_VER):]
        i = contents.find("#")
        return contents[:i].strip()
