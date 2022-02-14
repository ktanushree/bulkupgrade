#!/usr/bin/env python
"""
Prisma SDWAN Bulk Device Upgrades
tkamath@paloaltonetworks.com
Version: 1.0.1 b1
"""
# standard modules
import getpass
import json
import logging
import datetime
import os
import sys
import csv
import time
import numpy as np
import pandas as pd

#standard modules
import argparse
import logging

# CloudGenix Python SDK
import cloudgenix
import codecs

# Global Vars
SDK_VERSION = cloudgenix.version
SCRIPT_NAME = 'Prisma SD-WAN: Bulk Device Upgrade'
CSVHEADER = ["serial_number","software_version","download_time","upgrade_time","interfaces","download_interval","upgrade_interval"]
CSVHEADER_ABORT = ["serial_number"]

# Set NON-SYSLOG logging to use function name
logger = logging.getLogger(__name__)

sys.path.append(os.getcwd())
try:
    from cloudgenix_settings import CLOUDGENIX_AUTH_TOKEN

except ImportError:
    # Get AUTH_TOKEN/X_AUTH_TOKEN from env variable, if it exists. X_AUTH_TOKEN takes priority.
    if "X_AUTH_TOKEN" in os.environ:
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('X_AUTH_TOKEN')
    elif "AUTH_TOKEN" in os.environ:
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
    else:
        # not set
        CLOUDGENIX_AUTH_TOKEN = None

try:
    from cloudgenix_settings import CLOUDGENIX_USER, CLOUDGENIX_PASSWORD

except ImportError:
    # will get caught below
    CLOUDGENIX_USER = None
    CLOUDGENIX_PASSWORD = None


#
# Global Dicts
#
elem_id_name = {}
elem_name_id = {}
elem_id_hwid = {}
elem_hwid_id = {}
elemid_sid = {}
site_id_name = {}
site_name_id = {}
image_id_name = {}
image_name_id = {}
unsupported_id_name = {}
unsupported_name_id = {}
intf_id_name = {}
intf_name_id = {}
hwid_sid = {}


def create_dicts(cgx_session):
    print("Creating Translation Dicts..")
    print("\tSites")
    resp = cgx_session.get.sites()
    if resp.cgx_status:
        sitelist = resp.cgx_content.get("items", None)
        for site in sitelist:
            site_id_name[site["id"]] = site["name"]
            site_name_id[site["name"]] = site["id"]
    else:
        print("ERR: Could not retrieve sites")
        cloudgenix.jd_detailed(resp)

    print("\tElements & Interfaces")
    resp = cgx_session.get.elements()
    if resp.cgx_status:
        elemlist = resp.cgx_content.get("items", None)
        for elem in elemlist:
            sid = elem["site_id"]
            elem_id_name[elem["id"]] = elem["name"]
            elem_name_id[elem["name"]] = elem["id"]
            elem_id_hwid[elem["id"]] = elem["hw_id"]
            elem_hwid_id[elem["hw_id"]] = elem["id"]
            hwid_sid[elem["hw_id"]] = sid
            elemid_sid[elem["id"]] = sid

            if sid in ["1", 1]:
                continue
            else:
                resp = cgx_session.get.interfaces(site_id = sid, element_id=elem["id"])
                if resp.cgx_status:
                    intflist = resp.cgx_content.get("items", None)
                    for intf in intflist:
                        intf_id_name[(sid,elem["id"],intf["id"])] = intf["name"]
                        intf_name_id[(sid,elem["id"],intf["name"])] = intf["id"]

    else:
        print("ERR: Could not retrieve elements")
        cloudgenix.jd_detailed(resp)

    print("\tElement Images")
    resp = cgx_session.get.element_images()
    if resp.cgx_status:
        imagelist = resp.cgx_content.get("items", None)
        for image in imagelist:
            if image["state"] == "release":
                image_id_name[image["id"]] = image["version"]
                image_name_id[image["version"]] = image["id"]
            else:
                unsupported_id_name[image["id"]] = image["version"]
                unsupported_name_id[image["version"]] = image["id"]

    else:
        print("ERR: Could not retrieve element images")
        cloudgenix.jd_detailed(resp)

    return


def remove_bom(line):
    return line[3:] if line.startswith(codecs.BOM_UTF8) else line


def abort_upgrades(devicelist, cgx_session):
    for i, row in devicelist.iterrows():
        hwid = row["serial_number"]
        if hwid in elem_hwid_id.keys():
            elemid = elem_hwid_id[hwid]

            data = {
                "action": "abort_upgrade",
                "parameters": None
            }

            resp = cgx_session.post.operations_e(element_id=elemid, data=data)
            if resp.cgx_status:
                print("Upgrade aborted for {}".format(hwid))
            else:
                print("ERR: Could not abort upgrade for {}".format(hwid))
                cloudgenix.jd_detailed(resp)

    return


def upgrade_device(device_data,cgx_session):

    for i,row in device_data.iterrows():
        hwid = row["serial_number"]
        if hwid in elem_hwid_id.keys():
            elemid = elem_hwid_id[hwid]
            sid = elemid_sid[elemid]
            swversion = row["software_version"]

            if swversion in image_name_id.keys():
                imageid = image_name_id[swversion]


                intf_list = []
                interfaces_str = row["interfaces"]
                if interfaces_str is not None:
                    print(interfaces_str)
                    interfaces = interfaces_str.split(",")
                    if sid in ["1", 1]:
                        print("WARN: Device is not assigned to a site. Ignoring Interface settings for upgrade.")
                        intf_list = None
                    else:
                        for intf in interfaces:
                            if (sid, elemid, intf) in intf_name_id.keys():
                                iid = intf_name_id[(sid, elemid, intf)]
                                intf_list.append(iid)

                            else:
                                print("ERR: Interface {} not found on Device {}. Ignoring Interface settings for upgrade.".format(
                                        intf, hwid))

                if intf_list is not None:
                    if len(intf_list) == 0:
                        intf_list = None

                download_time = row["download_time"]
                upgrade_time = row["upgrade_time"]
                download_interval = row["download_interval"]
                upgrade_interval = row["upgrade_interval"]

                #
                # Get Current Software Status
                #
                resp = cgx_session.get.software_state(element_id=elemid)
                if resp.cgx_status:
                    status = resp.cgx_content
                    current_imageid = status["image_id"]
                    if current_imageid == imageid:
                        print("INFO: Device {} already at {}. Skipping Upgrade..".format(hwid,swversion))

                    else:
                        status["image_id"] = imageid
                        status["scheduled_download"] = download_time
                        status["scheduled_upgrade"] = upgrade_time
                        status["interface_ids"] = intf_list
                        status["download_interval"] = download_interval
                        status["upgrade_interval"] = upgrade_interval

                        resp = cgx_session.put.software_state(element_id=elemid,data=status)
                        if resp.cgx_status:
                            print("INFO: Device {} upgrade to {} scheduled".format(hwid,swversion))

                        else:
                            print("ERR: Device {} could not be upgraded to {}".format(hwid,swversion))
                            cloudgenix.jd_detailed(resp)

                else:
                    print("ERR: Could not retrieve software status")
                    cloudgenix.jd_detailed(resp)

            elif swversion in unsupported_name_id.keys():
                print("ERR: [CSV Row {}] Image {} is not longer supported. Please choose a different software image".format((i+1),swversion))
                continue

            else:
                print("ERR: [CSV Row {}] Invalid Software Image {}".format((i+1),swversion))
                continue
        else:
            print("ERR: [CSV Row {}] Device {} not found. Please check the Serial Number".format((i+1),hwid))
            continue


    return


def go():
    ############################################################################
    # Begin Script, parse arguments.
    ############################################################################

    # Parse arguments
    parser = argparse.ArgumentParser(description="{0}.".format(SCRIPT_NAME))

    # Allow Controller modification and debug level sets.
    controller_group = parser.add_argument_group('API', 'These options change how this program connects to the API.')
    controller_group.add_argument("--controller", "-C",
                                  help="Controller URI, ex. "
                                       "C-Prod: https://api.elcapitan.cloudgenix.com",
                                  default=None)

    controller_group.add_argument("--insecure", "-I", help="Disable SSL certificate and hostname verification",
                                  dest='verify', action='store_false', default=False)

    login_group = parser.add_argument_group('Login', 'These options allow skipping of interactive login')
    login_group.add_argument("--email", "-E", help="Use this email as User Name instead of prompting",
                             default=None)
    login_group.add_argument("--pass", "-PW", help="Use this Password instead of prompting",
                             default=None)

    # Commandline for CSV file name
    device_group = parser.add_argument_group('Device CSV', 'CSV file containing device and upgrade information')
    device_group.add_argument("--filename", "-F", help="Name of the file with path. "
                                                       "CSV file should contain the follow headers: "
                                                       "serial_number,software_version,download_time,upgrade_time,interfaces,download_interval,upgrade_interval", default=None)

    device_group.add_argument("--abort", "-A", help="Abort Scheduled Upgrades",
                              default=False, action="store_true")

    debug_group = parser.add_argument_group('Debug', 'These options enable debugging output')
    debug_group.add_argument("--debug", "-D", help="Verbose Debug info, levels 0-2", type=int,
                             default=0)

    args = vars(parser.parse_args())

    abort = args["abort"]

    if args['debug'] == 1:
        logging.basicConfig(level=logging.INFO,
                            format="%(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s")
        logger.setLevel(logging.INFO)
    elif args['debug'] >= 2:
        logging.basicConfig(level=logging.DEBUG,
                            format="%(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s")
        logger.setLevel(logging.DEBUG)
    else:
        # Remove all handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        # set logging level to default
        logger.setLevel(logging.WARNING)

    ############################################################################
    # Instantiate API
    ############################################################################
    cgx_session = cloudgenix.API(controller=args["controller"], ssl_verify=args["verify"])

    # set debug
    cgx_session.set_debug(args["debug"])
    ############################################################################
    # Draw Interactive login banner, run interactive login including args above.
    ############################################################################

    print("{0} v{1} ({2})\n".format(SCRIPT_NAME, SDK_VERSION, cgx_session.controller))

    filename = args["filename"]
    if not os.path.exists(filename):
        print("ERR: File not found. Please provide the entire path")
        sys.exit()
    else:
        csvdata = pd.read_csv(filename)
        csvdata = csvdata.replace({np.nan: None})
        columns = csvdata.columns.values

        if abort:
            if "serial_number" not in columns:
                print("ERR: Invalid CSV file format!\nCSV Header:{}\nPlease include column: serial_number".format(columns))
                sys.exit()
        else:
            if set(columns) != set(CSVHEADER):
                print("ERR: Invalid CSV file format!\nCSV Header:{}\nExpected Header:{}".format(columns,CSVHEADER))
                sys.exit()


    # login logic. Use cmdline if set, use AUTH_TOKEN next, finally user/pass from config file, then prompt.
    # figure out user
    if args["email"]:
        user_email = args["email"]
    elif CLOUDGENIX_USER:
        user_email = CLOUDGENIX_USER
    else:
        user_email = None

    # figure out password
    if args["pass"]:
        user_password = args["pass"]
    elif CLOUDGENIX_PASSWORD:
        user_password = CLOUDGENIX_PASSWORD
    else:
        user_password = None

    # check for token
    if CLOUDGENIX_AUTH_TOKEN and not args["email"] and not args["pass"]:
        cgx_session.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
        if cgx_session.tenant_id is None:
            print("AUTH_TOKEN login failure, please check token.")
            sys.exit()

    else:
        while cgx_session.tenant_id is None:
            cgx_session.interactive.login(user_email, user_password)
            # clear after one failed login, force relogin.
            if not cgx_session.tenant_id:
                user_email = None
                user_password = None

    ############################################################################
    # Create Translation Dicts
    ############################################################################
    create_dicts(cgx_session)
    if abort:
        print("INFO: Aborting scheduled upgrades")
        abort_upgrades(devicelist=csvdata, cgx_session=cgx_session)

    else:
        print("INFO: Performing Bulk Device Upgrades")
        upgrade_device(device_data=csvdata,cgx_session=cgx_session)
    # get time now.
    curtime_str = datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    # create file-system friendly tenant str.
    tenant_str = "".join(x for x in cgx_session.tenant_name if x.isalnum()).lower()

    # end of script, run logout to clear session.
    print("Logging Out.")
    cgx_session.get.logout()


if __name__ == "__main__":
    go()