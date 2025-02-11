################################################################################################################
#--------------------------------------------------bulkley---------------------------------------------------
################################################################################################################
path <- "/Volumes/backup_2022/backups/new_graph/uav_imagery/skeena/bulkley"
grep_this <- "/2024/"
recurse_level <- 1
invert_this <- TRUE
Volumes/backup_2022/backups/new_graph/uav_imagery/imagery_uav_bc
################################################################################################################
#--------------------------------------------------morice---------------------------------------------------
################################################################################################################

path <- "/Volumes/backup_2022/backups/new_graph/uav_imagery/skeena/morice"
grep_this <- "/2024/"
recurse_level <- 1
invert_this <- TRUE

################################################################################################################
#--------------------------------------------------babine zymoetz kispiox---------------------------------------------------
################################################################################################################

path <- "/Volumes/backup_2022/backups/new_graph/uav_imagery/skeena"
grep_this <- "/babine/|/kispiox/|/zymoetz/"
recurse_level <- 2
invert_this <- FALSE

################################################################################################################
#--------------------------------------------------babine zymoetz kispiox---------------------------------------------------
################################################################################################################

path <- "/Volumes/backup_2022/backups/new_graph/uav_imagery/mackenzie"
grep_this <- "$^"
recurse_level <- 2
invert_this <- TRUE

paths_raw <- fs::dir_ls(path,
                    recurse = recurse_level,
                    type = "dir",
                    # so we don't feed upper level directories (ex. 2023) this regex captures only those paths whose 
                    # last component is a number, excluding any paths with additional components beyond that. obviously
                    # we invert it to exclude them after
                    regexp = "^.*\\/\\d+$",
                    invert = TRUE
                    ) 

# now - we have already processes the imagery for 2024 so we will not repeat.  we will filter out those that contain /2024/
paths <- grep(grep_this, paths_raw, invert = invert_this, value = TRUE)

args <- lapply(paths, ngr::ngr_spk_odm)

args |>
  purrr::walk(
    ~ processx::run(
      command = "docker",
      args = .x,
      echo = TRUE
    )
  )

# to stop the computer from sleeping we ran the following in  the terminal
# caffeinate -s Rscript /Users/airvine/Projects/repo/stac_uav_bc/scripts/r/odm_process.R

