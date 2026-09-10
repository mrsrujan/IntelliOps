include "env" {
  path   = find_in_parent_folders()
  expose = true
}

# Skipped in this account: the AWS Kinesis control plane returns
# SubscriptionRequiredException for this account (even though IAM
# allows CreateStream via AdministratorAccess). Nothing downstream
# consumes kinesis outputs, so it is safe to leave un-applied.
skip = true

terraform {
  source = "../../../modules//kinesis"
}
