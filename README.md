# Prisma SDWAN Bulk ION Upgrade
This script is used to initiate bulk upgrade on Prisma SD-WAN ION devices. 

#### Synopsis
This script can be used to issue upgrades across multiple Prisma SD-WAN IONs in your network.  
Devices to be upgrades need to be provided in a CSV file. The script allows the end user to schedule both the software download and upgrade time, in addition to acceptable timeouts for these operations.
The script can also be used to abort scheduled upgrades.

To schedule an upgrade, the script expects a CSV with the following headers:

CSVHEADER = ["serial_number","software_version","download_time","upgrade_time","interfaces", "download_interval", "upgrade_interval"]

To abort upgrades, you can reuse the CSV file used to schedule the upgrade or a new file with the list of device serial numbers where upgrade needs to be aborted.
Make sure the column is named "serial_number".

#### Requirements
* Active Prisma SDWAN Account
* Python >=3.6
* Python modules:
    * Prisma SDWAN (CloudGenix) Python SDK >= 5.5.3b1 - <https://github.com/CloudGenix/sdk-python>

#### License
MIT

#### Installation:
 - **Github:** Download files to a local directory, manually run `bulkupgrade.py`. 

### Example of usage:
Bulk Upgrade IONs from CSV
```
./bulkupgrade.py -F devicedata.csv
```
Abort scheduled upgrades on IONs from CSV
```
./bulkupgrade.py -F devicedata.csv --abort
```
```
./bulkupgrade.py -A -F devicedata.csv 
```

#### Help Text:
```angular2
TanushreesMacbook:bulkupgrade tkamath$ ./bulkupgrade.py -h
usage: bulkupgrade.py [-h] [--controller CONTROLLER] [--insecure] [--email EMAIL] [--pass PASS] [--filename FILENAME] [--abort] [--debug DEBUG]

Prisma SD-WAN: Bulk Device Upgrade.

optional arguments:
  -h, --help            show this help message and exit

API:
  These options change how this program connects to the API.

  --controller CONTROLLER, -C CONTROLLER
                        Controller URI, ex. C-Prod: https://api.elcapitan.cloudgenix.com
  --insecure, -I        Disable SSL certificate and hostname verification

Login:
  These options allow skipping of interactive login

  --email EMAIL, -E EMAIL
                        Use this email as User Name instead of prompting
  --pass PASS, -PW PASS
                        Use this Password instead of prompting

Device CSV:
  CSV file containing device and upgrade information

  --filename FILENAME, -F FILENAME
                        Name of the file with path. CSV file should contain the follow headers: serial_number,software_version,download_time,upgrade_time,interfaces,download_interval,upgrade_interval
  --abort, -A           Abort Scheduled Upgrades

Debug:
  These options enable debugging output

  --debug DEBUG, -D DEBUG
                        Verbose Debug info, levels 0-2
TanushreesMacbook:bulkupgrade tkamath$ 
```

#### Version
| Version | Build | Changes |
| ------- | ----- | ------- |
| **1.0.1** | **b1** | Added support to abort upgrades |
| **1.0.0** | **b1** | Initial Release. |


#### For more info
 * Get help and additional Prisma SDWAN Documentation at <https://docs.paloaltonetworks.com/prisma/prisma-sd-wan.html>
