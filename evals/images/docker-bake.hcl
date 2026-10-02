# The two images every evals/smoke task builds on. evals/bin/build-images.sh
# sets the variables (from skills.config.json, or git refs) and runs
#   docker buildx bake -f evals/images/docker-bake.hcl --load
# The stack target reads eval-base through a target context, so the pair
# builds in one bake on any buildx driver.

variable "ASTRA_TOOLS" {}
variable "ASTRA_PIN" {}
variable "LIGHTCONE_CLI" {}

group "default" {
  targets = ["eval-base", "smoke-stack"]
}

target "eval-base" {
  context = "eval-base"
  tags    = ["lightcone-eval-base"]
}

target "smoke-stack" {
  context  = "smoke-stack"
  contexts = { lightcone-eval-base = "target:eval-base" }
  tags     = ["lightcone-smoke-stack"]
  args = {
    ASTRA_TOOLS   = ASTRA_TOOLS
    ASTRA_PIN     = ASTRA_PIN
    LIGHTCONE_CLI = LIGHTCONE_CLI
  }
}
