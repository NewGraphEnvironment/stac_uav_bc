################################################################################################################
#--------------------------------------------------bulkley---------------------------------------------------
################################################################################################################
path <- "/Users/airvine/Projects/gis/uav_imagery/bulkley"
grep_this <- "/2024/"
recurse_level <- 1
invert_this <- TRUE

################################################################################################################
#--------------------------------------------------morice---------------------------------------------------
################################################################################################################

path <- "/Users/airvine/Projects/gis/uav_imagery/morice"
grep_this <- "/2024/"
recurse_level <- 1
invert_this <- TRUE

################################################################################################################
#--------------------------------------------------babine zymoetz kispiox---------------------------------------------------
################################################################################################################

path <- "/Users/airvine/Projects/gis/uav_imagery/skeena"
grep_this <- "/babine/|/kispiox/|/zymoetz/"
recurse_level <- 2
invert_this <- FALSE

################################################################################################################
#--------------------------------------------------mackenzie---------------------------------------------------
################################################################################################################

path <- "/Users/airvine/Projects/gis/uav_imagery/mackenzie"
# our regex doesn't really work that well. we need to naem the watersheds we want. need to tweak
grep_this <- ""
recurse_level <- 2
invert_this <- FALSE

# # this should be consistent for all watersheds above.... Turned off to run sakals below
# paths_raw <- fs::dir_ls(path,
#                         recurse = recurse_level,
#                         type = "dir",
#                         # so we don't feed upper level directories (ex. 2023) this regex captures only those paths whose 
#                         # last component is a number, excluding any paths with additional components beyond that. 
#                         # this one we invert = TRUEit to exclude them after
#                         # regexp = "^.*\\/\\d+$",
#                         regexp = "^.*\\/\\d{4}\\/[^\\/]+$",
#                         invert = FALSE
# ) 
# 
# # now - we have already processes the imagery for 2024 so we will not repeat.  we will filter out those that contain /2024/
# paths <- grep(grep_this, paths_raw, invert = invert_this, value = TRUE)
# 
# args <- lapply(paths, ngr::ngr_spk_odm)
# 
# args |>
#   purrr::walk(
#     ~ processx::run(
#       command = "docker",
#       args = .x,
#       echo = TRUE
#     )
#   )

################################################################################################################
#--------------------------------------------------sakals 20250402---------------------------------------------------
################################################################################################################

path <- "/Users/airvine/Projects/gis/uav_imagery/sakals"

# 20191015 didn't run - so try without the first one
paths <- fs::dir_ls(path, type = "dir")[2:7]

args <- lapply(paths, ngr::ngr_spk_odm)

# args |>
#   purrr::walk(
#     ~ processx::run(
#       command = "docker",
#       args = .x,
#       echo = TRUE
#     )
#   )



################################################################################################################
#--------------------------------------------------bulkley 2025a--------------------------------------------------
################################################################################################################

path <- "/Users/airvine/Projects/gis/uav_imagery/skeena/bulkley/2025"

# 20191015 didn't run - so try without the first one
paths <- fs::dir_ls(path, type = "dir")

args <- purrr::map(
  paths,
  purrr::partial(
    ngr::ngr_spk_odm,
    params_default = c("--dtm", "--dsm", "--pc-quality", "low", "--dem-resolution", "5")
  )
)

args |>
  purrr::walk(
    ~ processx::run(
      command = "docker",
      args = .x,
      echo = TRUE
    )
  )

# to stop the computer from sleeping we ran the following in  the terminal - make sure docker is running
# caffeinate -s Rscript /Users/airvine/Projects/repo/stac_uav_bc/scripts/odm_process.R
