import os
import sys
import time
from datetime import datetime
import oci

USER_OCID = os.environ.get("OCI_USER_OCID")
TENANCY_OCID = os.environ.get("OCI_TENANCY_OCID")
FINGERPRINT = os.environ.get("OCI_FINGERPRINT")
KEY_CONTENT = os.environ.get("OCI_KEY_CONTENT")
REGION = os.environ.get("OCI_REGION")
SSH_PUBLIC_KEY = os.environ.get("SSH_PUBLIC_KEY")
AD = os.environ.get("OCI_AD")
IMAGE_ID = os.environ.get("OCI_IMAGE_ID")
SUBNET_ID = os.environ.get("OCI_SUBNET_ID")

def get_compute_client():
    config = {
        "user": USER_OCID,
        "key_content": KEY_CONTENT,
        "fingerprint": FINGERPRINT,
        "tenancy": TENANCY_OCID,
        "region": REGION
    }
    oci.config.validate_config(config)
    return oci.core.ComputeClient(config), config

def check_existing_instance(compute, tenancy_id):
    instances = compute.list_instances(compartment_id=tenancy_id).data
    for inst in instances:
        if inst.display_name == "VPS" and inst.lifecycle_state not in ["TERMINATED", "TERMINATING"]:
            return inst
    return None

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connecting to Cloud Provider...")
    compute, config = get_compute_client()

    existing = check_existing_instance(compute, TENANCY_OCID)
    if existing:
        print(f"Target instance already exists. ID: {existing.id} (State: {existing.lifecycle_state})")
        sys.exit(0)

    launch_details = oci.core.models.LaunchInstanceDetails(
        compartment_id=TENANCY_OCID,
        availability_domain=AD,
        display_name="VPS",
        shape="VM.Standard.A1.Flex",
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=2.0,
            memory_in_gbs=12.0
        ),
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            image_id=IMAGE_ID,
            boot_volume_size_in_gbs=50
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=SUBNET_ID,
            assign_public_ip=True,
            display_name="VPS-VNIC"
        ),
        metadata={
            "ssh_authorized_keys": SSH_PUBLIC_KEY
        }
    )

    max_duration_seconds = 5 * 3600
    start_time = time.time()
    attempt = 1

    print("Running worker task loop...")

    while time.time() - start_time < max_duration_seconds:
        current_time_str = datetime.now().strftime('%H:%M:%S')
        try:
            print(f"[{current_time_str}] Attempt #{attempt}...")
            inst = compute.launch_instance(launch_details).data
            print("\nInstance successfully provisioned!")
            print(f"ID: {inst.id}")
            sys.exit(0)
        except oci.exceptions.ServiceError as e:
            if e.status in [500, 429] or "Out of host capacity" in str(e.message):
                print(f"[{current_time_str}] Host capacity unavailable. Retrying in 60s...")
            else:
                print(f"[{current_time_str}] Error: {e}")
                sys.exit(1)
        except Exception as ex:
            print(f"[{current_time_str}] Exception: {ex}")
            time.sleep(10)

        attempt += 1
        time.sleep(60)

    print("Worker loop finished. Next schedule will resume.")
    sys.exit(0)

if __name__ == "__main__":
    main()
