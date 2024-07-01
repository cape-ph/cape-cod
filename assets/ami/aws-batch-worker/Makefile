.PHONY: check-packer
check-packer:
	@bash -c "if ! command -v packer &> /dev/null; then echo 'ERROR: packer could not be found. Make sure it is installed and in the PATH'; exit 1; fi"

.PHONY: init
init:
	packer init .

.PHONY: check-region
check-region:
	@bash -c "if [ -z ${REGION} ]; then echo 'ERROR: REGION variable must be set. Example: \"REGION=us-west-2 make al2\"'; exit 1; fi"

.PHONY: validate
validate: check-region init
	packer validate -var "region=${REGION}" .

release-al2023.auto.pkrvars.hcl:
	echo "Missing configuration file: release-al2023.auto.pkrvars.hcl."
	exit 1

.PHONY: al2023
al2023: check-region init validate release-al2023.auto.pkrvars.hcl
	packer build -only="amazon-ebs.al2023" -var "region=${REGION}" .
