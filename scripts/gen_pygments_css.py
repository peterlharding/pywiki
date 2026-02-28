from pygments.formatters import HtmlFormatter
css = HtmlFormatter(style="friendly").get_style_defs(".highlight")
with open("app/static/css/pygments.css", "w") as f:
    f.write(css)
print("Written app/static/css/pygments.css")
