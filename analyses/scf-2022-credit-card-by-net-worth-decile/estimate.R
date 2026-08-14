#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(haven)
  library(readr)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3) {
  stop("Usage: estimate.R SUMMARY.csv REPLICATE_WEIGHTS.dta OUTPUT.csv")
}

summary_path <- args[[1]]
replicate_path <- args[[2]]
output_path <- args[[3]]

weighted_decile_stats <- function(networth, balance, weight, stable_id) {
  valid <- is.finite(networth) & is.finite(balance) & is.finite(weight) & weight > 0
  networth <- networth[valid]
  balance <- balance[valid]
  weight <- weight[valid]
  stable_id <- stable_id[valid]
  ordering <- order(networth, stable_id)
  midpoint_share <- (cumsum(weight[ordering]) - weight[ordering] / 2) / sum(weight)
  decile_ordered <- pmin(10L, floor(midpoint_share * 10) + 1L)
  decile <- integer(length(ordering))
  decile[ordering] <- decile_ordered
  means <- vapply(
    1:10,
    function(group) weighted.mean(balance[decile == group], weight[decile == group]),
    numeric(1)
  )
  totals <- vapply(1:10, function(group) sum(weight[decile == group]), numeric(1))
  counts <- vapply(1:10, function(group) sum(decile == group), integer(1))
  list(mean = means, total = totals, count = counts)
}

scf <- read_csv(
  summary_path,
  col_select = c(YY1, Y1, WGT, NETWORTH, CCBAL),
  show_col_types = FALSE
) %>%
  mutate(IMPLICATE = Y1 %% 10L)

if (!setequal(as.integer(unique(scf$IMPLICATE)), 1:5)) {
  stop("The summary extract does not contain exactly five implicates")
}
if (any(table(scf$YY1) != 5L)) {
  stop("Each SCF family must have exactly five summary-extract records")
}

implicate_stats <- lapply(
  1:5,
  function(implicate) {
    subset <- scf[scf$IMPLICATE == implicate, ]
    weighted_decile_stats(subset$NETWORTH, subset$CCBAL, subset$WGT, subset$YY1)
  }
)
implicate_estimates <- do.call(rbind, lapply(implicate_stats, `[[`, "mean"))
point_estimate <- colMeans(implicate_estimates)
imputation_variance <- apply(implicate_estimates, 2, var)
# WGT is divided by five across the five implicates. Restore population scale
# for counts; this constant scaling cancels from all weighted mean estimates.
weighted_households <- 5 * colMeans(do.call(rbind, lapply(implicate_stats, `[[`, "total")))
unweighted_families <- round(colMeans(do.call(rbind, lapply(implicate_stats, `[[`, "count"))))

first <- scf %>%
  filter(IMPLICATE == 1L) %>%
  select(YY1, Y1, NETWORTH, CCBAL, WGT)
replicate_weights <- read_dta(replicate_path)
required_weight_columns <- paste0("wt1b", 1:999)
required_multiplicity_columns <- paste0("mm", 1:999)
missing_weights <- setdiff(
  c("y1", required_weight_columns, required_multiplicity_columns),
  names(replicate_weights)
)
if (length(missing_weights) > 0) {
  stop(paste("Replicate-weight file is incomplete:", paste(missing_weights, collapse = ", ")))
}

replicate_data <- first %>%
  inner_join(replicate_weights, by = c("Y1" = "y1"))
if (nrow(replicate_data) != nrow(first)) {
  stop("Replicate weights did not join one-to-one to first-implicate families")
}

replicate_estimates <- matrix(NA_real_, nrow = 999, ncol = 10)
for (index in 1:999) {
  replicate_weight <- replicate_data[[paste0("wt1b", index)]] *
    replicate_data[[paste0("mm", index)]]
  replicate_estimates[index, ] <- weighted_decile_stats(
    replicate_data$NETWORTH,
    replicate_data$CCBAL,
    replicate_weight,
    replicate_data$YY1
  )$mean
  if (index %% 100 == 0) message("Processed replicate ", index, " of 999")
}

sampling_variance <- apply(replicate_estimates, 2, var)
standard_error <- sqrt(sampling_variance + (6 / 5) * imputation_variance)

output <- tibble(
  decile = as.character(1:10),
  estimate = point_estimate,
  standard_error = standard_error,
  ci_low = point_estimate - 1.96 * standard_error,
  ci_high = point_estimate + 1.96 * standard_error,
  unweighted_families = unweighted_families,
  weighted_households = weighted_households,
  survey = "2022 Survey of Consumer Finances",
  variable = "CCBAL"
)

dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
write_csv(output, output_path)
