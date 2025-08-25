import json
import googleapiclient
from google.oauth2 import service_account
from googleapiclient import discovery

# ------------------------------------------------------------------------------
# GCP Based Validation of API Callers (EXAMPLE)
# ------------------------------------------------------------------------------
# There are 3 examples here based on Project, IP, and GKE Cluster lookup. All
# Require some metadata be passed in a http header.
#
# The following prerequisites exist on the GCP side for all examples:
#   - An IAM custom role created with the minimum of permissions needed
#   - A service account created with the custom role assigned to it.
#   - A service account key is exported to be used to authenticate to GCP
#     - Keep this safe. It is a credential
# -----------------------------------------------------------------------------

# --- Load Service Account Credentials From Key File ---
# --- Configuration ---
key_path = "./my-service-account-keyfile.json"

try:
    credentials = service_account.Credentials.from_service_account_file(
        key_path
    )
    print("Successfully loaded credentials from key file.")
except FileNotFoundError:
    print(f"ERROR: Service account key file not found at: {key_path}")
    exit(1)
except Exception as e:
    print(f"ERROR: Could not load credentials: {e}")
    exit(1)

# ------------------------------------------------------------------------------
# Project Lookup
# ------------------------------------------------------------------------------
# GCP Projects have an 'id' and a 'number'. Both are globally unique. Projects
# are looked up by id. A possible solution would be to pass the id in a
# header and initiate a lookup of project id using GCP APIs. The validation
# could be either simple API lookup succeeded or check that the returned project
# number is in an allow list.
#
# Must pass:
#   - project_id (alpha numeric)
#
# Permissions required:
#   - resourcemanager.projects.get
# -----------------------------------------------------------------------------

# --- Configuration ---
project_id = "my-project"
project_allow_list = ["112233445566"]

# --- Build Cloud Resource Manager API Client ---
try:
    service = discovery.build("cloudresourcemanager", "v3", credentials=credentials)
except Exception as e:
    print(f"ERROR: Could not build API client: {e}")
    exit(1)

# --- Describe Project ---
try:
    print(f"Describing project: {project_id}")
    # The projects().get() method requires the name to be in the format 'projects/PROJECT_ID'
    project_name = f"projects/{project_id}"
    request = service.projects().get(name=project_name)
    response = request.execute()

    print("\n--- Project Description ---")
    print(json.dumps(response, indent=2))
    print("--- End of Project Description ---")

    project_number = response.get("name").split("/")[-1]
    if project_number in project_allow_list:
        print(f"\nFound Project Number: {project_number} in Allow List")
    else:
        print(f"\nError: Project {project_id} not found in Allow List")

except Exception as e:
    print(f"ERROR: Failed to describe project {project_id}: {e}")
    print("Possible reasons:")
    print(
        "- The service account may not have the 'resourcemanager.projects.get' permission on this project."
    )
    print("- The project ID might be incorrect.")
    print(
        "- Cloud Resource Manager API might not be enabled in the project associated with the service account."
    )

# ------------------------------------------------------------------------------
# IP Address lookup
# ------------------------------------------------------------------------------
# IP Addresses must be looked up by resource name with the project & region also
# specified. A possible solution would be to pass the IP name(s), project, and
# region in a header and initiate a lookup of IP addresses using the GCP APIs.
# Once the IP address matching the source IP is found the validation is
# successful. This is complicated by a number of factors:
# 1. NAT devices, and therefore IPs, will be specific to each BMAP GCP region.
# 2. NAT devices autoscale by default (adding IPs). We need to control/limit this
#    to ensure that the workloads know the correct IP to pass in the header
#
# Must pass:
#   - project_id (alpha numeric)
#   - region
#   - IP resource name(s) - there might be more than one per region
#
# Permissions required:
#   - compute.addresses.get
# -----------------------------------------------------------------------------

# --- Configuration ---
project_id = "my-project"
address_region = "us-central1"
address_name = "us-central1-nat-ip01"
address_allow_list = ["34.107.21.167", "34.107.21.168"]

# --- Build Compute Engine API Client ---
try:
    service = discovery.build("compute", "v1", credentials=credentials)
except Exception as e:
    print(f"ERROR: Could not build API client: {e}")
    exit(1)

# --- Get Specific IP Address by Name and Region ---
try:
    print(
        f"\nLooking up address: {address_name} in project: {project_id}, region: {address_region}"
    )
    request = service.addresses().get(
        project=project_id, region=address_region, address=address_name
    )
    response = request.execute()

    print("\n--- Address Details ---")
    print(json.dumps(response, indent=2))
    print("--- End of Address Details ---")

    ip_address = response.get("address")
    if ip_address in address_allow_list:
        print(f"\nFound IP Address: {ip_address} in Allow List")
    else:
        print(f"\nError: Address {address_name} not found in Allow List")

except googleapiclient.errors.HttpError as e:
    if e.resp.status == 403:
        print(
            f"ERROR: Permission denied. The service account likely needs 'compute.addresses.get' permission."
        )
    elif e.resp.status == 404:
        print(
            f"ERROR: Address resource '{address_name}' not found in region '{address_region}' for project '{project_id}'."
        )
    else:
        print(f"ERROR: HTTP error occurred: {e}")
except Exception as e:
    print(f"ERROR: Failed to get address: {e}")


# ------------------------------------------------------------------------------
# GKE Cluster Lookup
# ------------------------------------------------------------------------------
# GKE Clusters must be looked up by name with the project & location also
# specified. A solution would be to pass the cluster name, project, and location
# and ensure that a successful response is returned from the GKE cluster
# describe API.
#
# Must pass:
#   - project_id (alpha numeric)
#   - location - GKE clusters can be regional or zonal. BMAP will always be region
#   - IP resource name(s) - there might be more than one per region
#
# Permissions required:
#   - container.clusters.get
# ------------------------------------------------------------------------------

# --- Configuration ---
project_id = "my-project"
cluster_name = "cluster-1"
# In GKE clusters may be regional or zonal, hence 'location'
# In BMAP they should always be regional
location = "us-central1"

# --- Build GKE API Client ---
try:
    service = discovery.build('container', 'v1', credentials=credentials)
except Exception as e:
    print(f"ERROR: Could not build API client: {e}")
    exit(1)

# --- Get Specific GKE Cluster ---
try:
    # Construct the full cluster name path
    cluster_resource_name = f"projects/{project_id}/locations/{location}/clusters/{cluster_name}"
    print(f"\nLooking up GKE cluster: {cluster_resource_name}")

    request = service.projects().locations().clusters().get(name=cluster_resource_name)
    response = request.execute()

    print("\n--- GKE Cluster Details ---")
    print(json.dumps(response, indent=2))
    print("--- End of GKE Cluster Details ---")

except googleapiclient.errors.HttpError as e:
    if e.resp.status == 403:
        print(f"ERROR: Permission denied. The service account likely needs 'container.clusters.get' permission.")
    elif e.resp.status == 404:
        print(f"ERROR: GKE Cluster '{cluster_name}' not found in location '{location}' for project '{project_id}'.")
    else:
        print(f"ERROR: HTTP error occurred: {e}")
except Exception as e:
    print(f"ERROR: Failed to get GKE cluster: {e}")
