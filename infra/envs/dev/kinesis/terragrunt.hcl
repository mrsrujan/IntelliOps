include "env" {
  path   = find_in_parent_folders()
  expose = true
}

terraform {
  source = "../../../modules//kinesis"
}
