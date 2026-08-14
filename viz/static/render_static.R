#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(ggplot2)
  library(ggtext)
  library(jsonlite)
  library(ragg)
  library(readr)
  library(scales)
  library(stringr)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3) {
  stop("Usage: render_static.R DATA.csv CHART.json OUTPUT.png")
}

data_path <- args[[1]]
config_path <- args[[2]]
output_path <- args[[3]]

config <- fromJSON(config_path, simplifyVector = TRUE)
data <- read_csv(data_path, show_col_types = FALSE)
if (xor(is.null(config$ci_low), is.null(config$ci_high))) {
  stop("ci_low and ci_high must be configured together")
}
required <- c(config$x, config$y, config$ci_low, config$ci_high)
if (config$chart_type == "choropleth") {
  required <- c(config$region_key, config$y, config$ci_low, config$ci_high)
}
required <- required[!vapply(required, is.null, logical(1))]
missing <- setdiff(required, names(data))
if (length(missing) > 0) {
  stop(paste("Missing chart columns:", paste(missing, collapse = ", ")))
}
# Continuous x-axis (line/area) keeps numeric ordering; categorical x (bar)
# uses the row order. Factor only bar charts: a discrete x with many levels
# (e.g. a 201-point wage grid) renders as an unreadable smear, and a factor
# x-axis breaks geom_area(position = "stack").
if (config$chart_type == "bar") {
  data[[config$x]] <- factor(data[[config$x]], levels = unique(data[[config$x]]))
}
palette <- c(
  navy = "#18354C",
  teal = "#008C95",
  blue = "#2F6BFF",
  red = "#D14B57",
  gold = "#CB8214",
  ink = "#17212B",
  muted = "#64717D",
  paper = "#FCFCFA"
)

# Editorial fidelity theme. Hex values extracted from the
# source article's own PNGs: paper #f8f7f5, gridlines #d9d9d9, series colors
# US #2d4d62 / Denmark #237a9f / Norway #a9c784 / Finland #f5a764 /
# Sweden #b5181a; SHA bands #c34446 / #4e93b0 / #f6b781 / #566f7f;
# title #111111, subtitle #333333, caption #666666. The compact type
# band (title ~24px, subtitle ~15px) keeps the plot panel at ~52-56% of
# the canvas like the originals, instead of letting the header dominate.
editorial_palette <- c(
  navy = "#2d4d62",
  blue = "#237a9f",
  teal = "#a9c784",
  gold = "#f5a764",
  red = "#b5181a",
  gov = "#c34446",
  comp = "#4e93b0",
  vol = "#f6b781",
  oop = "#566f7f",
  ink = "#111111",
  muted = "#333333",
  caption = "#666666",
  paper = "#f8f7f5",
  grid = "#d9d9d9"
)

theme_editorial <- function() {
  theme_minimal(base_family = "Jost", base_size = 17) +
    theme(
      plot.background = element_rect(fill = editorial_palette[["paper"]], color = NA),
      panel.background = element_rect(fill = editorial_palette[["paper"]], color = NA),
      plot.title = element_text(
        family = "Jost Black", face = "plain", size = 23,
        color = editorial_palette[["ink"]], margin = margin(b = 2)
      ),
      plot.subtitle = element_text(
        size = 15.5, color = editorial_palette[["muted"]], margin = margin(b = 8)
      ),
      plot.caption = element_text(
        size = 13, color = editorial_palette[["caption"]], hjust = 0,
        lineheight = 1.15, margin = margin(t = 14)
      ),
      axis.title = element_text(
        face = "bold", size = 14, color = editorial_palette[["muted"]]
      ),
      axis.title.x = element_text(margin = margin(t = 10)),
      axis.title.y = element_text(margin = margin(r = 10)),
      axis.text = element_text(size = 15, color = editorial_palette[["ink"]]),
      panel.grid.major = element_line(color = editorial_palette[["grid"]], linewidth = 0.5),
      panel.grid.minor = element_blank(),
      axis.ticks = element_blank(),
      legend.position = "none",
      plot.margin = margin(40, 36, 16, 24)
    )
}

# Bauhaus / De Stijl fidelity theme. Principles applied:
# - Form follows function; reduction to essential geometry (no ornament,
#   no chartjunk, flat planes — no transparency, no gradients).
# - Primary colors only: red, blue, yellow, plus black, white, grey
#   (Mondrian). Series map onto the primaries; US is black.
# - Orthogonal black lines as structure: panel frame, axes, and the
#   separators between stacked bands are all pure black.
# - Geometric sans (Jost Black, a Futura revival) in lowercase for the
#   headline; lowercase everywhere is the Bauhaus typographic signature.
# - Asymmetric composition: plot panel sits left of center.
bauhaus_palette <- c(
  red = "#E32636",
  blue = "#2456E6",
  yellow = "#F5C400",
  black = "#0A0A0A",
  grey = "#8A8A8A",
  white = "#FFFFFF",
  paper = "#FAF9F6"
)

theme_policy_bauhaus <- function() {
  theme_minimal(base_family = "Jost", base_size = 17) +
    theme(
      plot.background = element_rect(fill = bauhaus_palette[["paper"]], color = NA),
      panel.background = element_rect(fill = bauhaus_palette[["paper"]], color = NA),
      plot.title = element_text(
        family = "Jost Black", face = "plain", size = 26,
        color = bauhaus_palette[["black"]], margin = margin(b = 4)
      ),
      plot.subtitle = element_text(
        size = 15.5, color = bauhaus_palette[["grey"]], margin = margin(b = 10)
      ),
      plot.caption = element_text(
        size = 12.5, color = bauhaus_palette[["grey"]], hjust = 0,
        lineheight = 1.2, margin = margin(t = 14)
      ),
      axis.title = element_text(
        face = "bold", size = 14, color = bauhaus_palette[["black"]]
      ),
      axis.title.x = element_text(margin = margin(t = 10)),
      axis.title.y = element_text(margin = margin(r = 10)),
      axis.text = element_text(size = 15, color = bauhaus_palette[["black"]]),
      panel.grid.major = element_line(color = bauhaus_palette[["grey"]], linewidth = 0.4),
      panel.grid.minor = element_blank(),
      axis.ticks = element_line(color = bauhaus_palette[["black"]], linewidth = 0.6),
      axis.ticks.length = unit(0.12, "cm"),
      panel.border = element_rect(
        fill = NA, color = bauhaus_palette[["black"]], linewidth = 1.6
      ),
      legend.position = "none",
      plot.margin = margin(40, 36, 16, 24)
    )
}

# Swiss Style (International Typographic Style) theme. Principles applied
# (Müller-Brockmann / Hofmann / Ruder):
# - Grotesque sans-serif (Helvetica lineage; Liberation Sans is the system
#   clone) — not the geometric Futura voice of Bauhaus.
# - Asymmetric, flush-left composition; nothing centered; generous
#   whitespace as the active design element.
# - The grid is a visible feature: hairline rules, no boxed frames.
# - Functional colour: monochrome greys/black with a single red accent
#   reserved for the subject series.
# - The eyebrow: a small, letter-spaced, uppercase category label above the
#   headline — the signature International Typographic Style device.
swiss_palette <- c(
  red = "#E30613",
  blue = "#2456E6",
  yellow = "#F5C400",
  green = "#1E8A3C",
  black = "#111111",
  grey = "#6E6E6E",
  hairline = "#D8D8D8",
  paper = "#FFFFFF"
)

theme_policy_swiss <- function() {
  theme_minimal(base_family = "Liberation Sans", base_size = 17) +
    theme(
      plot.background = element_rect(fill = swiss_palette[["paper"]], color = NA),
      panel.background = element_rect(fill = swiss_palette[["paper"]], color = NA),
      plot.title = element_markdown(
        family = "Liberation Sans", face = "bold", size = 27,
        color = swiss_palette[["black"]], hjust = 0, margin = margin(b = 6)
      ),
      plot.subtitle = element_text(
        size = 15.5, color = swiss_palette[["grey"]], hjust = 0,
        margin = margin(b = 12)
      ),
      plot.caption = element_text(
        size = 12.5, color = swiss_palette[["grey"]], hjust = 0,
        lineheight = 1.2, margin = margin(t = 14)
      ),
      plot.tag = element_text(
        family = "Liberation Sans", size = 12, face = "bold",
        color = swiss_palette[["red"]], hjust = 0, margin = margin(b = 14)
      ),
      plot.tag.position = c(0.02, 0.99),
      axis.title = element_text(
        face = "bold", size = 14, color = swiss_palette[["black"]]
      ),
      axis.title.x = element_text(margin = margin(t = 10)),
      axis.title.y = element_text(margin = margin(r = 10)),
      axis.text = element_text(size = 14.5, color = swiss_palette[["black"]]),
      panel.grid.major = element_line(color = swiss_palette[["hairline"]], linewidth = 0.35),
      panel.grid.minor = element_blank(),
      axis.ticks = element_line(color = swiss_palette[["black"]], linewidth = 0.4),
      axis.ticks.length = unit(0.1, "cm"),
      legend.position = "none",
      plot.margin = margin(44, 48, 20, 40)
    )
}
color <- if (!is.null(config$color)) config$color else palette[["teal"]]
orientation <- if (!is.null(config$orientation)) config$orientation else "vertical"
chart_type <- config$chart_type

# Select theme by config: editorial fidelity, bauhaus, swiss, or default.
use_editorial <- !is.null(config$theme) && config$theme == "editorial"
use_bauhaus <- !is.null(config$theme) && config$theme == "bauhaus"
use_swiss <- !is.null(config$theme) && config$theme == "swiss"
theme_use <- function() {
  if (use_editorial) theme_editorial()
  else if (use_bauhaus) theme_policy_bauhaus()
  else if (use_swiss) theme_policy_swiss()
  else theme_policy()
}
series_color_map <- function() {
  if (!is.null(config$color_map)) {
    unlist(config$color_map)
  } else if (use_swiss) {
    # Distinct primaries — red for the subject series (US), then blue,
    # yellow, green, black for the Nordics. No grey ladder: series must be
    # separable at a glance.
    c(
      "United States" = swiss_palette[["red"]],
      # US variant: dashed red — same family as the subject series, so the
      # legend never shows two identical-looking black series.
      "United States + Health Insurance" = swiss_palette[["red"]],
      "Denmark" = swiss_palette[["blue"]],
      "Finland" = swiss_palette[["yellow"]],
      "Norway" = swiss_palette[["green"]],
      "Sweden" = swiss_palette[["black"]],
      "Canada" = swiss_palette[["grey"]],
      "United Kingdom" = swiss_palette[["grey"]],
      "Germany" = swiss_palette[["grey"]],
      "France" = swiss_palette[["grey"]]
    )
  } else if (use_bauhaus) {
    c(
      "United States" = bauhaus_palette[["black"]],
      "United States + Health Insurance" = bauhaus_palette[["black"]],
      "Denmark" = bauhaus_palette[["blue"]],
      "Finland" = bauhaus_palette[["yellow"]],
      "Norway" = bauhaus_palette[["grey"]],
      "Sweden" = bauhaus_palette[["red"]],
      "Canada" = bauhaus_palette[["grey"]],
      "United Kingdom" = bauhaus_palette[["grey"]],
      "Germany" = bauhaus_palette[["grey"]],
      "France" = bauhaus_palette[["grey"]]
    )
  } else if (use_editorial) {
    c(
      "United States" = editorial_palette[["navy"]],
      "United States + Health Insurance" = editorial_palette[["navy"]],
      "Denmark" = editorial_palette[["blue"]],
      "Finland" = editorial_palette[["gold"]],
      "Norway" = editorial_palette[["teal"]],
      "Sweden" = editorial_palette[["red"]],
      "Canada" = editorial_palette[["muted"]],
      "United Kingdom" = editorial_palette[["muted"]],
      "Germany" = editorial_palette[["muted"]],
      "France" = editorial_palette[["muted"]]
    )
  } else {
    c(
      "United States" = palette[["navy"]],
      "United States + Health Insurance" = palette[["navy"]],
      "Denmark" = palette[["blue"]],
      "Finland" = palette[["gold"]],
      "Norway" = palette[["teal"]],
      "Sweden" = palette[["red"]],
      "Canada" = palette[["muted"]],
      "United Kingdom" = palette[["muted"]],
      "Germany" = palette[["muted"]],
      "France" = palette[["muted"]]
    )
  }
}
fill_color_map <- function() {
  if (use_swiss) {
    # Distinct primaries for each band, red for the headline band.
    c(
      "Government programs" = swiss_palette[["red"]],
      "Compulsory private" = swiss_palette[["blue"]],
      "Voluntary private" = swiss_palette[["yellow"]],
      "Out-of-pocket" = swiss_palette[["green"]]
    )
  } else if (use_bauhaus) {
    # Mondrian planes: primary red, primary blue, primary yellow, plus
    # black and grey for neutral planes.
    c(
      "Government programs" = bauhaus_palette[["red"]],
      "Compulsory private" = bauhaus_palette[["blue"]],
      "Voluntary private" = bauhaus_palette[["yellow"]],
      "Out-of-pocket" = bauhaus_palette[["grey"]]
    )
  } else if (use_editorial) {
    c(
      "Government programs" = editorial_palette[["gov"]],
      "Compulsory private" = editorial_palette[["comp"]],
      "Voluntary private" = editorial_palette[["vol"]],
      "Out-of-pocket" = editorial_palette[["oop"]]
    )
  } else {
    c(
      "Government programs" = palette[["red"]],
      "Compulsory private" = palette[["blue"]],
      "Voluntary private" = palette[["gold"]],
      "Out-of-pocket" = palette[["muted"]]
    )
  }
}

format_value <- function(values) {
  format_name <- if (!is.null(config$value_format)) config$value_format else "number"
  if (format_name == "percent") return(label_percent(accuracy = 0.1)(values))
  if (format_name == "currency") return(label_dollar(accuracy = 1, big.mark = ",")(values))
  if (format_name == "compact_currency") return(label_dollar(scale_cut = cut_short_scale())(values))
  label_comma(accuracy = 0.1)(values)
}

# Axis tick labels. Fidelity mode is active when any suffix is configured
# (y tick_suffix, or an explicit x_tick_suffix): labels become whole
# numbers (no thousands separators) plus the per-axis suffix. When no
# suffix is configured anywhere, fall back to the data formatter so
# existing charts keep their decimal labels byte-for-byte.
fidelity_mode <- nzchar(config$tick_suffix) || !is.null(config$x_tick_suffix)
x_suffix <- if (!is.null(config$x_tick_suffix)) config$x_tick_suffix else config$tick_suffix
y_suffix <- config$tick_suffix

tick_label <- function(values, suffix) {
  if (!fidelity_mode) return(format_value(values))
  labels <- as.character(round(values))
  if (nzchar(suffix)) paste0(labels, suffix) else labels
}

theme_policy <- function() {
  theme_minimal(base_family = "Roboto", base_size = 20) +
    theme(
      plot.background = element_rect(fill = palette[["paper"]], color = NA),
      panel.background = element_rect(fill = palette[["paper"]], color = NA),
      plot.title = element_textbox_simple(
        family = "Roboto Condensed", face = "bold", size = 34,
        color = palette[["ink"]], lineheight = 1.03,
        margin = margin(b = 8)
      ),
      plot.subtitle = element_text(
        size = 19, color = palette[["muted"]], lineheight = 1.15,
        margin = margin(b = 22)
      ),
      plot.caption = element_text(
        size = 12.5, color = palette[["muted"]], hjust = 0,
        lineheight = 1.15, margin = margin(t = 22)
      ),
      axis.title.x = element_text(
        family = "Roboto Condensed", face = "bold", size = 15,
        color = palette[["muted"]], margin = margin(t = 13)
      ),
      axis.title.y = element_text(
        family = "Roboto Condensed", face = "bold", size = 15,
        color = palette[["muted"]], margin = margin(r = 13)
      ),
      axis.text = element_text(size = 16, color = palette[["ink"]]),
      panel.grid.major = element_line(color = "#D9DEE2", linewidth = 0.45),
      panel.grid.minor = element_blank(),
      axis.ticks = element_blank(),
      legend.position = "none",
      plot.margin = margin(36, 46, 30, 36)
    )
}

caption <- str_wrap(paste0("Source: ", config$source), width = 95)
if (!is.null(config$note) && nzchar(config$note)) {
  caption <- paste(caption, str_wrap(config$note, width = 95), sep = "\n")
}

# Editorial theme renders lines noticeably thicker than the default theme.
line_w <- if (use_editorial) 1.9 else if (use_bauhaus || use_swiss) 2.4 else 1.6

if (chart_type == "bar" && orientation == "horizontal") {
  # Horizontal bars: same grouped/fill machinery as vertical bars, with
  # x = value (continuous) and y = category (discrete, reordered by value).
  fill_col <- if (!is.null(config$series)) config$series else config$x
  fill_levels <- unique(data[[fill_col]])
  # Value labels computed up front (before ggplot captures the data) so the
  # layer can reference the column. With ratio_label set, stamp the ratio on
  # the subject (first color_map key or first series) bar instead of its value.
  group_col <- if (!is.null(config$series)) config$series else config$x
  subject_group <- if (!is.null(config$ratio_label)) {
    if (!is.null(config$color_map)) names(unlist(config$color_map))[[1]] else fill_levels[[1]]
  } else NULL
  if (!is.null(subject_group)) {
    ratio_suffix <- if (!is.null(config$ratio_suffix) && nzchar(config$ratio_suffix)) config$ratio_suffix else "\u00d7"
    ratio_vals <- suppressWarnings(as.numeric(data[[config$ratio_label]]))
    ratio_text <- vapply(ratio_vals, function(rv) {
      if (is.na(rv)) return(NA_character_)
      txt <- format(round(rv, 1), nsmall = 1, trim = TRUE)
      sub("\\.0$", "", txt)  # 14.0 -> 14, keep 14.1
    }, character(1))
    has_ratio <- data[[group_col]] == subject_group & !is.na(ratio_vals)
    data[[".label"]] <- ifelse(
      has_ratio,
      paste0(ratio_text, ratio_suffix),
      format_value(data[[config$y]])
    )
  } else {
    data[[".label"]] <- format_value(data[[config$y]])
  }
  if (!is.null(config$color_map)) {
    cmap <- unlist(config$color_map)
    bar_fills <- vapply(
      fill_levels,
      function(lbl) {
        if (lbl %in% names(cmap)) cmap[[lbl]]
        else if (use_swiss) swiss_palette[["grey"]]
        else color
      },
      character(1)
    )
  } else {
    bar_fills <- vapply(
      fill_levels,
      function(lbl) {
        if (use_swiss && lbl == "United States") swiss_palette[["red"]]
        else if (use_swiss) swiss_palette[["grey"]]
        else color
      },
      character(1)
    )
  }
  plot <- ggplot(data, aes(x = .data[[config$y]], y = .data[[config$x]], fill = .data[[fill_col]])) +
    geom_col(
      position = if (!is.null(config$series)) "dodge" else "identity",
      width = 0.68,
      show.legend = !is.null(config$series)
    ) +
    scale_fill_manual(values = bar_fills) +
    scale_x_continuous(labels = format_value, expand = expansion(mult = c(0, 0.14))) +
    {if (is.null(config$show_value_labels) || config$show_value_labels) {
      geom_text(
        aes(x = .data[[config$y]], label = .data[[".label"]]),
        hjust = -0.35, family = if (use_swiss) "Liberation Sans" else "Roboto Condensed",
        fontface = "bold", size = 5.2, color = palette[["ink"]]
      )
    }} +
    theme_use() +
    theme(
      panel.grid.major.y = element_blank(),
      legend.position = if (!is.null(config$series)) "top" else "none",
      legend.title = element_blank(),
      legend.spacing.x = unit(1.4, "lines"),
      legend.key.width = unit(1.8, "lines"),
      legend.text = element_text(
        size = 14,
        family = if (use_editorial || use_bauhaus) "Jost" else if (use_swiss) "Liberation Sans" else "Roboto Condensed",
        color = if (use_editorial) editorial_palette[["ink"]] else if (use_bauhaus) bauhaus_palette[["black"]] else if (use_swiss) swiss_palette[["black"]] else palette[["ink"]],
        margin = margin(r = 14)
      )
    )
} else if (chart_type == "bar") {
  # Fill column: grouped bars use `series`;
  # plain bars use the x category itself. Per-category fills come from
  # config$color_map when present, else a theme heuristic that highlights
  # the United States category with the accent and
  # neutrals everything else (user feedback: no same-color bars side by side).
  fill_col <- if (!is.null(config$series)) config$series else config$x
  fill_levels <- unique(data[[fill_col]])
  if (!is.null(config$color_map)) {
    cmap <- unlist(config$color_map)
    bar_fills <- vapply(
      fill_levels,
      function(lbl) {
        if (lbl %in% names(cmap)) cmap[[lbl]]
        else if (use_swiss) swiss_palette[["grey"]]
        else color
      },
      character(1)
    )
  } else {
    bar_fills <- vapply(
      fill_levels,
      function(lbl) {
        if (use_swiss && lbl == "United States") swiss_palette[["red"]]
        else if (use_swiss) swiss_palette[["grey"]]
        else color
      },
      character(1)
    )
  }
  plot <- ggplot(data, aes(x = .data[[config$x]], y = .data[[config$y]], fill = .data[[fill_col]])) +
    geom_col(position = if (!is.null(config$series)) "dodge" else "identity",
             width = 0.68,
             show.legend = !is.null(config$series)) +
    scale_fill_manual(values = bar_fills) +
    {if (is.null(config$show_value_labels) || config$show_value_labels) {
      geom_text(
        aes(
          y = if (!is.null(config$ci_high)) .data[[config$ci_high]] else .data[[config$y]],
          label = format_value(.data[[config$y]])
        ),
        vjust = -0.55, family = if (use_swiss) "Liberation Sans" else "Roboto Condensed",
        fontface = "bold", size = 5.2,
        color = palette[["ink"]]
      )
    }} +
    scale_y_continuous(labels = function(v) tick_label(v, y_suffix), expand = expansion(mult = c(0, 0.14))) +
    theme_use() +
    theme(
      panel.grid.major.x = element_blank(),
      legend.position = if (!is.null(config$series)) "top" else "none",
      legend.title = element_blank(),
      legend.spacing.x = unit(1.4, "lines"),
      legend.key.width = unit(1.8, "lines"),
      legend.text = element_text(
        size = 14,
        family = if (use_editorial || use_bauhaus) "Jost" else if (use_swiss) "Liberation Sans" else "Roboto Condensed",
        color = if (use_editorial) editorial_palette[["ink"]] else if (use_bauhaus) bauhaus_palette[["black"]] else if (use_swiss) swiss_palette[["black"]] else palette[["ink"]],
        margin = margin(r = 14)
      )
    )
} else if (chart_type == "line" && !is.null(config$series)) {
  if (!is.null(config$series_order)) {
    data[[config$series]] <- factor(
      data[[config$series]],
      levels = unlist(config$series_order)
    )
  }
  # Per-series linetype (solid/dashed) for article-style series like
  # "United States + Health Insurance". Defaults to solid; must cover EVERY
  # series level or ggplot drops unmatched ones from the plot entirely.
  configured_styles <- if (!is.null(config$line_style)) unlist(config$line_style) else NULL
  all_levels <- if (is.factor(data[[config$series]])) {
    levels(data[[config$series]])
  } else {
    unique(data[[config$series]])
  }
  line_styles <- setNames(rep("solid", length(all_levels)), all_levels)
  if (!is.null(configured_styles)) {
    for (name in names(configured_styles)) {
      if (name %in% all_levels) line_styles[[name]] <- configured_styles[[name]]
    }
  }
  plot <- ggplot(data, aes(x = .data[[config$x]], y = .data[[config$y]], color = .data[[config$series]], group = .data[[config$series]])) +
    geom_line(aes(linetype = .data[[config$series]]), linewidth = line_w, lineend = "round") +
    scale_linetype_manual(values = line_styles) +
    scale_y_continuous(
      labels = function(v) tick_label(v, y_suffix),
      breaks = if (!is.null(config$y_ticks)) unlist(config$y_ticks) else waiver(),
      limits = if (!is.null(config$y_min) || !is.null(config$y_max)) c(config$y_min, config$y_max) else NULL,
      expand = expansion(mult = c(0.04, 0.12))
    ) +
    scale_x_continuous(
      breaks = if (!is.null(config$x_ticks)) unlist(config$x_ticks) else waiver(),
      labels = function(v) tick_label(v, x_suffix)
    ) +
    scale_color_manual(values = series_color_map()) +
    theme_use() +
    theme(
      panel.grid.major.x = element_blank(),
      legend.position = "top",
      legend.title = element_blank(),
      legend.spacing.x = unit(1.4, "lines"),
      legend.key.width = unit(1.8, "lines"),
      legend.text = element_text(
        size = 14,
        family = if (use_editorial || use_bauhaus) "Jost" else if (use_swiss) "Liberation Sans" else "Roboto Condensed",
        color = if (use_editorial) editorial_palette[["ink"]] else if (use_bauhaus) bauhaus_palette[["black"]] else if (use_swiss) swiss_palette[["black"]] else palette[["ink"]],
        margin = margin(r = 14)
      )
    )
} else if (chart_type == "area" && !is.null(config$series)) {
  # ggplot stacks with the first factor level at the top. To reproduce the
  # intended financing stack (bottom to top: Out-of-pocket, Voluntary
  # private, Compulsory private, Government programs) the levels must run
  # top to bottom. The legend mirrors the stack top-to-bottom, so legend
  # order and stack order agree visually.
  data[[config$series]] <- factor(
    data[[config$series]],
    levels = c(
      "Government programs",
      "Compulsory private",
      "Voluntary private",
      "Out-of-pocket"
    )
  )
  plot <- ggplot(data, aes(x = .data[[config$x]], y = .data[[config$y]], fill = .data[[config$series]])) +
    # Bauhaus: flat color planes (alpha 1). A black outline on every band
    # traces the stacked boundaries — the De Stijl black-grid lines.
    geom_area(
      position = "stack",
      alpha = if (use_bauhaus) 1 else 0.92,
      color = if (use_bauhaus) bauhaus_palette[["black"]] else NA,
      linewidth = 0.5
    ) +
    scale_x_continuous(
      breaks = if (!is.null(config$x_ticks)) unlist(config$x_ticks) else seq(1970, 2025, by = 5),
      labels = function(v) tick_label(v, x_suffix)
    ) +
    scale_y_continuous(
      labels = function(v) tick_label(v, y_suffix),
      breaks = if (!is.null(config$y_ticks)) unlist(config$y_ticks) else waiver(),
      limits = if (!is.null(config$y_min) || !is.null(config$y_max)) c(config$y_min, config$y_max) else NULL,
      expand = expansion(mult = c(0.02, 0.1))
    ) +
    scale_fill_manual(values = fill_color_map()) +
    theme_use() +
    theme(
      panel.grid.major.x = element_blank(),
      legend.position = "top",
      legend.title = element_blank(),
      legend.text = element_text(
        size = 14,
        family = if (use_editorial || use_bauhaus) "Jost" else if (use_swiss) "Liberation Sans" else "Roboto Condensed",
        color = if (use_editorial) editorial_palette[["ink"]] else if (use_bauhaus) bauhaus_palette[["black"]] else if (use_swiss) swiss_palette[["black"]] else palette[["ink"]],
        margin = margin(r = 14)
      )
    ) +
    guides(fill = guide_legend(reverse = TRUE))

  # De Stijl: explicit black boundary lines at each interior stack level.
  # A plain color outline on stacked geom_area gets covered by the band
  # drawn above, so trace the cumulative boundaries as their own lines.
  if (use_bauhaus) {
    bd <- data[, c(config$x, config$series, config$y)]
    names(bd) <- c("x", "series", "y")
    levs_bottom_up <- rev(levels(data[[config$series]]))  # Out-of-pocket, Voluntary, Compulsory, Government
    bd$series <- factor(bd$series, levels = levs_bottom_up)
    bd <- bd[order(bd$x, bd$series), ]
    # Cumulative value per x in stack order: the boundary above each band.
    bd$cum <- ave(bd$y, bd$x, FUN = cumsum)
    # Every stack level except the top carries an interior boundary line.
    bounds <- bd[bd$series != levs_bottom_up[length(levs_bottom_up)], ]
    plot <- plot + geom_line(
      data = bounds, aes(x = x, y = cum, group = series, fill = NULL),
      color = bauhaus_palette[["black"]], linewidth = 1.4
    )
  }
} else if (chart_type == "line") {
  plot <- ggplot(data, aes(x = .data[[config$x]], y = .data[[config$y]], group = 1)) +
    geom_line(color = color, linewidth = 1.8, lineend = "round") +
    geom_point(color = color, size = 3.8) +
    scale_y_continuous(labels = format_value, expand = expansion(mult = c(0.04, 0.12))) +
    theme_use() +
    theme(panel.grid.major.x = element_blank())
} else if (chart_type == "ribbon") {
  # Two series with the gap between them shaded. Wide-format: one row per
  # band with v1/v2 from the two series; ribbon fills min..max, lines trace
  # each series.
  series_key <- config$series
  s_levels <- unique(data[[series_key]])
  s1 <- s_levels[[1]]
  s2 <- s_levels[[2]]
  bands <- unique(data[[config$x]])
  wide <- data.frame(
    band = bands,
    v1 = vapply(bands, function(b) {
      hit <- data[[config$x]] == b & data[[series_key]] == s1
      ifelse(any(hit), data[[config$y]][hit][[1]], NA_real_)
    }, numeric(1)),
    v2 = vapply(bands, function(b) {
      hit <- data[[config$x]] == b & data[[series_key]] == s2
      ifelse(any(hit), data[[config$y]][hit][[1]], NA_real_)
    }, numeric(1))
  )
  wide$lo <- pmin(wide$v1, wide$v2, na.rm = TRUE)
  wide$hi <- pmax(wide$v1, wide$v2, na.rm = TRUE)
  cmap <- if (!is.null(config$color_map)) unlist(config$color_map) else NULL
  c1 <- if (!is.null(cmap) && s1 %in% names(cmap)) cmap[[s1]]
  else if (use_swiss && s1 == "United States") swiss_palette[["red"]]
  else if (use_swiss) swiss_palette[["grey"]]
  else color
  c2 <- if (!is.null(cmap) && s2 %in% names(cmap)) cmap[[s2]]
  else if (use_swiss && s2 == "United States") swiss_palette[["red"]]
  else if (use_swiss) swiss_palette[["grey"]]
  else ink
  ribbon_fill <- if (use_swiss) "#F2C9CC" else "#BFD8DC"
  wide[[config$x]] <- factor(wide$band, levels = bands)
  plot <- ggplot(wide, aes(x = .data[[config$x]])) +
    geom_ribbon(aes(ymin = lo, ymax = hi, group = 1), fill = ribbon_fill, alpha = 0.9) +
    geom_line(aes(y = v1, group = 1, color = s1), linewidth = line_w, lineend = "round") +
    geom_line(aes(y = v2, group = 1, color = s2), linewidth = line_w, lineend = "round") +
    geom_point(aes(y = v1, color = s1), size = 3.4) +
    geom_point(aes(y = v2, color = s2), size = 3.4) +
    scale_color_manual(
      values = setNames(c(c1, c2), c(s1, s2))
    ) +
    scale_y_continuous(labels = format_value, expand = expansion(mult = c(0.04, 0.12))) +
    theme_use() +
    theme(
      panel.grid.major.x = element_blank(),
      legend.position = "top",
      legend.title = element_blank()
    )
} else if (chart_type == "dumbbell") {
  # Per-category pair of points + connector; the connector length IS the
  # gap. Horizontal: y = category, x = value.
  series_key <- config$series
  s_levels <- unique(data[[series_key]])
  s1 <- s_levels[[1]]
  s2 <- s_levels[[2]]
  bands <- unique(data[[config$x]])
  wide <- data.frame(
    band = bands,
    v1 = vapply(bands, function(b) {
      hit <- data[[config$x]] == b & data[[series_key]] == s1
      ifelse(any(hit), data[[config$y]][hit][[1]], NA_real_)
    }, numeric(1)),
    v2 = vapply(bands, function(b) {
      hit <- data[[config$x]] == b & data[[series_key]] == s2
      ifelse(any(hit), data[[config$y]][hit][[1]], NA_real_)
    }, numeric(1))
  )
  cmap <- if (!is.null(config$color_map)) unlist(config$color_map) else NULL
  c1 <- if (!is.null(cmap) && s1 %in% names(cmap)) cmap[[s1]]
  else if (use_swiss && s1 == "United States") swiss_palette[["red"]]
  else if (use_swiss) swiss_palette[["grey"]]
  else color
  c2 <- if (!is.null(cmap) && s2 %in% names(cmap)) cmap[[s2]]
  else if (use_swiss && s2 == "United States") swiss_palette[["red"]]
  else if (use_swiss) swiss_palette[["grey"]]
  else ink
  wide[[config$x]] <- factor(wide$band, levels = bands)
  # Gap annotations next to the higher dot; legend maps the two series.
  wide$gap <- abs(wide$v2 - wide$v1)
  wide$rightmost <- pmax(wide$v1, wide$v2)
  plot <- ggplot(wide, aes(y = .data[[config$x]])) +
    geom_segment(aes(x = v1, xend = v2, yend = .data[[config$x]]),
                 color = if (use_swiss) "#9A9A9A" else palette[["muted"]],
                 linewidth = 1.6) +
    geom_point(aes(x = v1, color = s1), size = 6) +
    geom_point(aes(x = v2, color = s2), size = 6) +
    geom_text(
      aes(x = rightmost, label = paste0(format_value(gap))),
      hjust = -0.5, vjust = 0.5, size = 4.4, fontface = "bold",
      color = if (use_swiss) swiss_palette[["black"]] else palette[["ink"]]
    ) +
    scale_color_manual(values = setNames(c(c1, c2), c(s1, s2))) +
    scale_x_continuous(
      labels = format_value,
      limits = if (!is.null(config$y_min) && !is.null(config$y_max)) {
        c(config$y_min, config$y_max)
      } else {
        NULL
      },
      expand = expansion(mult = c(0.06, 0.18))
    ) +
    theme_use() +
    theme(
      panel.grid.major.y = element_blank(),
      legend.position = "top",
      legend.title = element_blank()
    )
} else if (chart_type == "ratio_ladder") {
  # Per-category marker on a shared ratio scale vs a reference line
  # (default 1.0). Horizontal: y = category, x = ratio.
  ref <- if (!is.null(config$reference)) config$reference else 1.0
  data[[config$x]] <- factor(data[[config$x]], levels = unique(data[[config$x]]))
  plot <- ggplot(data, aes(y = .data[[config$x]], x = .data[[config$y]])) +
    geom_vline(xintercept = ref, linetype = "dashed",
               color = if (use_swiss) "#9A9A9A" else palette[["muted"]], linewidth = 0.9) +
    geom_point(color = if (use_swiss) swiss_palette[["red"]] else color, size = 5.5) +
    geom_text(aes(label = paste0(format_value(.data[[config$y]]), "×")),
              hjust = -0.5, size = 4.6,
              family = if (use_swiss) "Liberation Sans" else "Roboto Condensed",
              color = palette[["ink"]]) +
    scale_x_continuous(labels = format_value, expand = expansion(mult = c(0.1, 0.18))) +
    theme_use() +
    theme(panel.grid.major.y = element_blank())
} else if (chart_type == "pictogram") {
  # Grid of glyphs per category row; filled count = round(share * 100).
  # glyph: "circle" | "coin" | "person". Person glyphs use a unicode
  # person; circles/coins use geom_point (shape 21) with white fill.
  rows <- list()
  for (i in seq_len(nrow(data))) {
    share <- as.numeric(data[[config$y]][[i]])
    filled <- round(share * 100)
    for (g in seq_len(100)) {
      rows[[length(rows) + 1]] <- data.frame(
        category = data[[config$x]][[i]],
        col = ((g - 1) %% 10) + 1,
        row = ((g - 1) %/% 10) + 1,
        filled = g <= filled
      )
    }
  }
  grid_data <- do.call(rbind, rows)
  grid_data$category <- factor(grid_data$category, levels = unique(data[[config$x]]))
  cat_count <- length(unique(data[[config$x]]))
  # Person glyphs: ragg renders Noto Color Emoji with its own palette (the
  # colour aesthetic is ignored), so the static renderer always draws
  # filled circles — the interactive keeps real person symbols. Static and
  # interactive share data/chart.yaml but need not share glyph fidelity.
  plot <- ggplot(grid_data, aes(x = col, y = row)) +
    geom_point(
      aes(fill = filled), shape = 21, size = 5.2,
      color = if (use_swiss) "#9A9A9A" else palette[["muted"]],
      stroke = 0.5
    ) +
    scale_fill_manual(values = c(`TRUE` = if (use_swiss) swiss_palette[["red"]] else color,
                                 `FALSE` = "#FFFFFF"),
                      guide = "none") +
    facet_wrap(vars(category), nrow = cat_count, strip.position = "left") +
    scale_x_continuous(breaks = NULL, expand = expansion(mult = c(0.08, 0.08))) +
    scale_y_reverse(breaks = NULL, expand = expansion(mult = c(0.1, 0.1))) +
    coord_fixed(ratio = 0.9, clip = "off") +
    theme_use() +
    theme(
      panel.grid = element_blank(),
      axis.ticks = element_blank(),
      axis.text = element_blank(),
      strip.text.y.left = element_text(
        angle = 0, hjust = 1, size = 13,
        family = if (use_swiss) "Liberation Sans" else "Roboto Condensed"
      ),
      strip.background = element_blank(),
      panel.spacing = unit(1.1, "lines")
    )
} else if (chart_type == "choropleth") {
  # US state map colored by value. Geometry: viz/assets/us-states-polygons.csv
  # (Census TIGER 5m simplified), joined to data on stusps/name/statfp.
  raw_args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", raw_args, value = TRUE)
  script_dir <- if (length(file_arg) > 0) {
    dirname(sub("^--file=", "", file_arg[[1]]))
  } else {
    getwd()
  }
  asset_path <- file.path(dirname(script_dir), "assets", "us-states-polygons.csv")
  if (!file.exists(asset_path)) {
    stop(paste("Missing state geometry:", asset_path))
  }
  states <- read_csv(asset_path, show_col_types = FALSE)
  # Geometry CSV: name, stusps, ring (per-state polygon id), order (vertex
  # index within ring), lon, lat. Each ring is its own group.
  states$ring_id <- as.numeric(factor(paste(states$stusps, states$ring, sep = ":")))
  region_key <- if (!is.null(config$region_key)) config$region_key else config$x
  region_format <- if (!is.null(config$region_format)) config$region_format else "stusps"
  states$region <- states[[region_format]]
  data[[region_key]] <- as.character(data[[region_key]])
  if (region_format == "name") {
    data[[region_key]] <- tolower(data[[region_key]])
    states$region <- tolower(states$region)
  }
  # Join by match() instead of merge(): merge() reorders rows alphabetically,
  # scrambling the per-ring point order that geom_polygon needs. match()
  # preserves the geometry's vertex order exactly.
  value_map <- setNames(as.numeric(data[[config$y]]), data[[region_key]])
  joined <- states
  joined$fill_val <- unname(value_map[joined$region])
  cmap <- if (!is.null(config$color_map)) unlist(config$color_map) else NULL
  fill_scale_vals <- joined[!is.na(joined$fill_val), ]
  if (nrow(fill_scale_vals) == 0) {
    plot <- ggplot(joined, aes(x = lon, y = lat, group = ring_id)) +
      geom_polygon(fill = "#EEF0F2", color = "#FFFFFF", linewidth = 0.35) +
      coord_quickmap() + theme_void() + theme_use()
  } else {
    max_v <- max(fill_scale_vals$fill_val, na.rm = TRUE)
    min_v <- min(fill_scale_vals$fill_val, na.rm = TRUE)
    # CVD-safe sequential ramp (ColorBrewer BuPu 6-step) per wiki 03:
    # light blue -> deep purple preserves the low->high luminance signal
    # for protan/deutan viewers, unlike the red-only swiss scale.
    bu_pu <- c("#E0ECF4", "#BFD3E6", "#9EBCDA", "#8C96C6", "#8C6BB1", "#88419D")
    joined$color_out <- vapply(seq_len(nrow(joined)), function(i) {
      v <- joined$fill_val[[i]]
      if (is.na(v)) return("#EDEDED")
      key <- joined$region[[i]]
      if (!is.null(cmap) && key %in% names(cmap)) return(cmap[[key]])
      if (v == max_v) return(bu_pu[[6]])
      if (v == min_v) return(bu_pu[[1]])
      idx <- 1 + round((v - min_v) / (max_v - min_v) * 5)
      bu_pu[[min(max(idx, 1), 6)]]
    }, character(1))
    plot <- ggplot(joined, aes(x = lon, y = lat, group = ring_id)) +
      geom_polygon(aes(fill = color_out), color = "#FFFFFF", linewidth = 0.35) +
      scale_fill_identity() +
      coord_quickmap() +
      theme_void() +
      theme_use() +
      theme(panel.grid = element_blank(), axis.text = element_blank())
  }
} else if (chart_type == "step") {
  # Monotone descent as a step area: shaded region + step line. The x
  # categories are discrete (poverty bands); geom_step with a numeric
  # position + band labels keeps the step geometry real. The shaded area
  # uses the same stepped y values (each band holds its level until the
  # next band) via stat="identity".
  bands <- unique(data[[config$x]])
  data[[".pos"]] <- match(data[[config$x]], bands) - 1
  # Step-interpolate the area: each band holds its y across the whole
  # interval, so the area follows the step, not a diagonal. A phantom point
  # one band-width past the last band gives the final plateau ("400%+") real
  # width instead of a zero-width vertical drop at the right edge.
  last_y <- data[[config$y]][nrow(data)]
  phantom <- data.frame(x = length(bands), y = last_y)
  # Step polygon: each interior boundary x appears twice (right edge of the
  # previous band, left edge of the next) and each y appears twice (left +
  # right edge of its own band). This makes the area a true step region.
  inner_x <- if (length(bands) > 1) rep(seq_len(length(bands) - 1), each = 2) else numeric(0)
  # Closed polygon: baseline corners (0,0) and (max,0) make the shape fill
  # down to zero; the step points connect in data order.
  step_seg <- data.frame(
    x = c(0, 0, inner_x, length(bands), length(bands)),
    y = c(0, rep(data[[config$y]], each = 2), 0)
  )
  step_line_data <- rbind(
    data.frame(x = data[[".pos"]], y = data[[config$y]]),
    phantom
  )
  plot <- ggplot() +
    # geom_polygon connects points in data order (no x-sorting), so the
    # step polygon stays a staircase. geom_area re-sorts by x and zigzags
    # on duplicate x values.
    geom_polygon(
      data = step_seg, aes(x = x, y = y),
      fill = if (use_swiss) "#F2D3D5" else "#C7E4E6",
      alpha = 0.9
    ) +
    geom_step(
      data = step_line_data, aes(x = x, y = y, color = "line"),
      direction = "hv", linewidth = 2.6
    ) +
    scale_x_continuous(
      breaks = seq_along(bands) - 1,
      labels = bands,
      expand = expansion(mult = c(0.02, 0.02))
    ) +
    scale_y_continuous(labels = format_value, expand = expansion(mult = c(0, 0.14))) +
    scale_color_manual(values = c(line = if (use_swiss) swiss_palette[["red"]] else color)) +
    guides(color = "none") +
    theme_use() +
    theme(
      axis.text.x = element_text(
        angle = if (use_swiss) 0 else 30,
        hjust = if (use_swiss) 0.5 else 1,
        size = if (use_swiss) 13 else 15
      )
    )
} else if (chart_type == "donut") {
  # One ring per category row; arc = share. coord_polar turns the stacked
  # bars into donut segments. Rows are faceted by category.
  donut_data <- data.frame(
    category = data[[config$x]],
    share = as.numeric(data[[config$y]]),
    rest = 1 - as.numeric(data[[config$y]])
  )
  donut_long <- tidyr::pivot_longer(donut_data, c("share", "rest"),
    names_to = "segment", values_to = "value")
  donut_long$category <- factor(donut_long$category, levels = unique(donut_data$category))
  donut_long$segment <- factor(donut_long$segment, levels = c("share", "rest"))
  plot <- ggplot(donut_long, aes(x = "", y = value, fill = segment)) +
    geom_bar(stat = "identity", width = 1, color = "#FFFFFF", linewidth = 0.8) +
    scale_fill_manual(
      values = c(share = if (use_swiss) swiss_palette[["red"]] else color,
                 rest = if (use_swiss) "#EDEDED" else "#D9DEE2"),
      guide = "none"
    ) +
    coord_polar(theta = "y", start = 0) +
    facet_wrap(vars(category), nrow = 1) +
    theme_void() +
    theme_use() +
    theme(
      panel.grid = element_blank(),
      axis.text = element_blank(),
      strip.text = element_text(
        size = 13,
        family = if (use_swiss) "Liberation Sans" else "Roboto Condensed",
        color = if (use_swiss) swiss_palette[["black"]] else palette[["ink"]]
      ),
      plot.margin = margin(30, 10, 10, 10)
    )
} else if (chart_type == "dot") {
  plot <- ggplot(data, aes(x = .data[[config$y]], y = .data[[config$x]])) +
    geom_point(color = color, size = 5) +
    scale_x_continuous(labels = format_value, expand = expansion(mult = c(0.08, 0.15))) +
    theme_use() +
    theme(panel.grid.major.y = element_blank())
} else {
  stop(paste("Unsupported chart type:", chart_type))
}

# CI error bars are banned (user directive 2026-08): no error bars are drawn.
# Interval bounds remain available in the fallback data table.

if (!is.null(config$vline) && length(config$vline) > 0) {
  # jsonlite auto-simplifies a uniform array of objects into a data frame;
  # normalize so we iterate over rows, not columns.
  vlines <- if (is.data.frame(config$vline)) {
    lapply(split(config$vline, seq_len(nrow(config$vline))), as.list)
  } else {
    config$vline
  }
  for (line in vlines) {
    plot <- plot + geom_vline(
      xintercept = as.numeric(line[["x"]]),
      linetype = if (!is.null(line[["linetype"]])) line[["linetype"]] else "dashed",
      color = if (!is.null(line[["color"]])) line[["color"]] else palette[["muted"]],
      linewidth = 0.9
    ) + annotate(
      "text",
      x = as.numeric(line[["x"]]),
      y = as.numeric(line[["label_y"]]),
      label = line[["label"]],
      hjust = if (!is.null(line[["hjust"]])) as.numeric(line[["hjust"]]) else -0.02,
      vjust = -0.5,
      size = 4.2,
      color = if (!is.null(line[["color"]])) line[["color"]] else palette[["muted"]],
      family = if (use_editorial || use_bauhaus) "Jost" else if (use_swiss) "Liberation Sans" else "Roboto Condensed"
    )
  }
  # Allow the annotation to extend past the panel edge instead of clipping.
  plot <- plot + coord_cartesian(clip = "off")
}

plot <- plot + labs(
  title = if (use_swiss && !is.null(config$eyebrow)) {
    paste0(
      "<span style='color:", swiss_palette[["red"]], ";font-size:13px;font-weight:700;letter-spacing:2.5px;'>", toupper(config$eyebrow), "</span><br>",
      # ggtext markdown collapses plain newlines to spaces, so a str_wrap'd
      # title renders as one long overflowing line; use explicit <br>.
      gsub("\n", "<br>", str_wrap(config$title, width = 54))
    )
  } else {
    str_wrap(config$title, width = 54)
  },
  subtitle = str_wrap(config$subtitle, width = 80),
  caption = caption,
  x = if (!is.null(config$x_label)) config$x_label else NULL,
  y = if (!is.null(config$y_label)) config$y_label else NULL,
  tag = NULL
)

width <- if (!is.null(config$width)) config$width else 1400
height <- if (!is.null(config$height)) config$height else 900
dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
agg_png(output_path, width = width, height = height, units = "px", res = 144, background = palette[["paper"]])
print(plot)
dev.off()
