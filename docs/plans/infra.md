# Terraform EC2 production deployment

## Goal

Replace the partially manual production deployment with a Terraform-provisioned EC2 host and GitHub OIDC/SSM deployment while leaving the existing production instance unchanged until a deliberate manual cutover.

The replacement will use:

- AWS account `844825014198`, region `us-west-2`
- existing private VPC `vpc-0d5da450de7b3e1ee`
- existing private subnet `subnet-0a49a0288c57235e1`
- `t3.small`
- Canonical Ubuntu 26.04 AMD64 AMI `ami-026ec9e84a2221297`
- existing ECR repository `beanlab/rubber-duck`
- existing S3 configuration bucket `rubber-duck-config`
- GitHub repository `beanlab/rubber-duck`

No implementation or validation step will mutate the current instance `i-0e82640083109edf2`. The new data volume starts empty; database migration and old-host shutdown are deferred to manual cutover.

## Current status

Repository implementation is complete on the `infra` branch and committed through `a13cf67` (`Automate production EC2 deployment`). No AWS resources have been created or changed by this implementation work, and the legacy production instance remains untouched.

Completed:

- documented the production deployment contract
- changed SES setup to use boto3's ambient credential chain and added focused tests
- added the committed Docker build and ignore files
- added bootstrap and production-environment Terraform roots with provider lock files
- added bootstrap, host-update, container-deployment, and health-check scripts
- rewrote the GitHub Actions workflow for the explicit `master -> production` path
- updated deployment, rollback, diagnostics, security-boundary, and manual-cutover documentation
- added explicit IAM denies protecting the legacy instance, security group, and root volume

Validated locally:

- both Terraform roots pass formatting and `terraform validate`
- all shell scripts pass `bash -n`
- the GitHub workflow parses and has the intended five-job structure
- the Docker image builds successfully and can import the application
- the 19 applicable Python tests pass, including the ambient-credential tests
- `git diff --check` passes

The complete Python suite is not currently green because of pre-existing test-harness issues: `tests/test_rubricize.py` imports unavailable `myteam.workflow`, and `tests/tester_bot_tests` expects an undeclared `--config` option when run from the root suite. These failures are unrelated to this deployment implementation.

Remaining work:

1. Refresh the expired `byu-cs-poweruser` AWS SSO session.
2. Perform final read-only AWS checks and review bootstrap/environment Terraform plans.
3. Prepare a mode-`400` or mode-`600` production runtime-secret JSON file and confirm the production configuration.
4. Run `aws/first-time-bootstrap.sh` to create/import shared resources, provision the replacement environment, populate Secrets Manager, and upload configuration.
5. Push and merge `infra` to `master`, then verify the GitHub OIDC deployment pipeline.
6. Smoke-test SSM, no-ingress networking, instance-profile credentials, S3, SES, Docker-socket tools, release metadata, and the empty persistent data volume without running two bots with the same Discord token.
7. During a coordinated manual cutover, stop the old container, copy SQLite to the new EBS volume, redeploy, verify production behavior, and manually take the old instance offline.
8. Deliberately replace the new EC2 instance and prove that a sentinel SQLite record survives on the persistent volume.

## 1. Framework refactor

One feature-neutral application change is required before static AWS credentials can be removed:

- Change `EmailSender` to create its SES client from boto3's default credential chain and configured/default AWS region rather than requiring `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
- Preserve email validation, message content, and failure behavior.
- Add a focused test proving client creation uses ambient credentials and an optional `AWS_REGION`.

No other application framework refactor is needed.

## 2. Feature addition

### Container build

- Add a top-level `Dockerfile` using Python 3.12 and Poetry, preserving the current source, dataset, rubric, and command layout.
- Add `.dockerignore` to exclude Git metadata, local secrets, databases, Terraform state, caches, tests, and scratch content.
- Reduce `.github/scripts/build_docker.sh` to a small wrapper around the committed Dockerfile, or remove workflow reliance on it.
- Build with `--pull`, a full-SHA environment tag, and OCI source/revision/created/environment labels.

### Terraform bootstrap root

Create `aws/terraform/bootstrap/{main,variables,outputs}.tf` and `aws/first-time-bootstrap.sh`.

The bootstrap command will:

1. Require AWS profile/account/region validation and protected runtime-secret JSON mode `400` or `600`.
2. Create `rubber-duck-terraform-state-844825014198` with AWS CLI only when absent.
3. Initialize directly into `rubber-duck/bootstrap/terraform.tfstate` using S3-native locking.
4. Import the bucket resources and existing GitHub OIDC provider when present.
5. Apply versioning, encryption, public-access blocking, the OIDC provider, and `rubber-duck-github-deploy` role.
6. Apply the production environment root once for initial provisioning, populate `/rubber-duck/production/runtime` directly in Secrets Manager, and upload the selected configuration to `environments/production/config.yaml`.

Secret values will never pass through Terraform, user data, S3, or command-line arguments. The bootstrap root will reference, not manage, the existing ECR and configuration buckets.

The GitHub trust policy will allow only `repo:beanlab/rubber-duck:ref:refs/heads/master`. The role will use the required enterprise permissions boundary and bounded Terraform/ECR/SSM permissions rather than an unrestricted `Action = "*"` policy.

### Terraform environment root

Create `aws/terraform/environment/{main,variables,outputs}.tf` and checked-in `environments/production.tfvars`.

Production state will use `rubber-duck/environments/production/terraform.tfstate`. Resources will include:

- a no-ingress security group with outbound access
- an encrypted persistent gp3 EBS data volume with deletion protection
- a production EC2 instance with no key pair or public IP
- an IAM role/profile with the enterprise boundary
- `AmazonSSMManagedInstanceCore`
- scoped ECR pull, Secrets Manager read, S3 read, and SES send permissions
- the runtime secret container, without any secret value
- volume attachment and environment/application/management tags

S3 read permissions will include the production configuration prefix and the currently configured runtime dataset objects in `stats121-datasets` and `byu-cms-metrics`. IMDSv2 will be required with hop limit 2 so bridge-networked containers can discover instance-profile credentials.

Changing the pinned AMI will replace the instance but retain and reattach the data volume.

### Instance lifecycle scripts

Add:

- `aws/scripts/instance-bootstrap.sh`
- `aws/scripts/update-host.sh`
- `aws/scripts/deploy-container.sh`
- `aws/scripts/health-check.sh`

Terraform will render multipart cloud-init that installs root-owned scripts and non-secret fixed settings. Bootstrap will install Ubuntu `docker.io`, enable Docker and the Canonical SSM agent, locate only the expected EBS volume by ID, format it only when blank, mount it at `/var/lib/rubber-duck`, persist the filesystem UUID in `fstab`, and bound journald retention.

Host updates will have one owner, emit exactly one reboot flag, and avoid upgrades during bootstrap. Deployment will lock with `flock`, authenticate to ECR through the instance profile, pull and run the digest URI, fetch a JSON secret into a temporary mode-600 env file, mount the persistent database and Docker socket, run the bounded health check, write release metadata atomically, remove temporary secrets with a trap, and prune images only after success.

### GitHub Actions

Rewrite `.github/workflows/ci-cd.yml` as one serialized production pipeline:

1. `prepare`: accept only `master`, derive canonical production outputs.
2. `build`: use OIDC, build the committed Dockerfile with full-SHA labels/tag, push, and resolve the ECR digest.
3. `provision`: initialize production remote state, format/validate/plan/apply, and export instance/AMI outputs.
4. `maintain`: wait for cloud-init and SSM, execute host updates, and handle a required reboot with bounded waits.
5. `deploy`: invoke the digest-pinned deployment through SSM, poll terminal states, and report deployment metadata.

The workflow will contain no static AWS credentials, generated secret files, config uploads, short SHAs, arbitrary branch names, or critical-path Discord notifications. Manual dispatch is accepted only from `master` and deploys that ref's resolved commit; rollback uses a revert on `master`, not an arbitrary-commit input.

### Documentation and legacy path

- Rewrite `docs/deployment.md` with bootstrap, normal deployment, diagnostics, rollback-by-revert, and manual database cutover instructions.
- Expand the README deployment summary.
- Keep `aws/restart_duck.sh` unchanged as a record of the old host procedure until cutover succeeds.
- Remove workflow reliance on obsolete S3 upload and inline Docker build helpers, but avoid deleting legacy helpers until the new path is proven.

## 3. Validation

Before any AWS mutation:

- run the full Python test suite
- run focused tests for ambient boto3 credential behavior
- run `bash -n` on all shell scripts
- run `terraform fmt -check` on both roots
- run offline `terraform init -backend=false` and `terraform validate` for both roots
- parse/check the GitHub workflow and Docker build configuration with available local tools
- inspect `git diff --check` and confirm the old instance ID is referenced only by an explicit IAM deny safeguard, never as an automation target

AWS creation and deployment happen only after repository changes and Terraform plans are reviewed. Acceptance will verify the new instance, SSM, no-ingress networking, digest-pinned container, instance-role credentials, empty persistent data volume, and replacement behavior without changing or stopping the old instance.
