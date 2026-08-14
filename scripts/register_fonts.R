#!/usr/bin/env Rscript
# Install the bundled Jost static weights into the user font directory and
# refresh the fontconfig cache so ragg (via systemfonts/fontconfig) can
# render Jost by family name.
#
# Jost is a geometric (Futura-like) sans, OFL-licensed, from Google Fonts
# (indestructible-type/Jost). The statics are instantiations of the official
# variable font (wght 100-900) at the weights the editorial fidelity theme uses:
#   Jost Black   900  -> headlines
#   Jost SemiBold 600 -> subhead/emphasis
#   Jost Medium   500 -> body
#   Jost Regular  400 -> captions and axes
#
# Idempotent: copying over the same files and re-running fc-cache is safe.
args <- commandArgs(trailingOnly = FALSE)
script_arg <- sub("^--file=", "", args[grep("^--file=", args)[1]])
if (!nzchar(script_arg)) stop("cannot locate script path")
root <- normalizePath(file.path(dirname(script_arg), ".."))
fonts_src <- file.path(root, "viz", "assets", "fonts")
fonts_dst <- file.path(Sys.getenv("HOME"), ".local", "share", "fonts")

statics <- c(
  "Jost-Regular.ttf", "Jost-Medium.ttf", "Jost-SemiBold.ttf",
  "Jost-Bold.ttf", "Jost-Black.ttf"
)
for (file in statics) {
  src <- file.path(fonts_src, file)
  if (!file.exists(src)) stop("missing font: ", src)
}
dir.create(fonts_dst, recursive = TRUE, showWarnings = FALSE)
file.copy(file.path(fonts_src, statics), fonts_dst, overwrite = TRUE)

status <- system("fc-cache -f >/dev/null 2>&1")
if (status != 0) warning("fc-cache failed; fonts may not be picked up")
cat("Installed", length(statics), "Jost weights to", fonts_dst, "\n")
