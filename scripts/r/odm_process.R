################################################################################################################
#--------------------------------------------------bulkley 2024---------------------------------------------------
################################################################################################################
# do this first to get it done
# re-processs the uav imagery at 10cm resolution for serving online
path <- "/Volumes/backup_2022/backups/new_graph/archive/uav_imagery/skeena/bulkley/2024"
paths <- fs::dir_ls(path,
                    glob = "barren|richfield",
                    invert = TRUE) 


# ?ngr::ngr_spk_odm


path <- "/Volumes/backup_2022/backups/new_graph/archive/uav_imagery/skeena/bulkley/2024"
paths <- fs::dir_ls(path,
                    glob = "barren|richfield",
                    invert = TRUE) 

args <- lapply(paths, ngr::ngr_spk_odm)

# args |> 
#   purrr::walk(
#     ~ processx::run(
#       command = "docker",
#       args = .x,
#       echo = TRUE
#     )
#   )
