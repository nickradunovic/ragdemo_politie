import json
import xmltodict
from datetime import date, datetime
import requests
import glob
import time
from pathlib import Path
import pandas as pd
import pathlib
import urllib
import multiprocessing
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import shutil
from tqdm import tqdm
from functools import partial


# Define empty lists where we'll store our data temporarily
ecli_df = []
full_text_df = []
creator_df = []
date_decision_df = []
issued_df = []
zaaknummer_df = []
type_df = []
relations_df = []
references_df = []
subject_df = []
procedure_df = []
inhoudsindicatie_df = []
hasVersion_df = []
threads = []
max_workers = 0

# Define base URL
RECHTSPRAAK_API_BASE_URL = (
    "https://data.rechtspraak.nl/uitspraken/zoeken?rechtsgebied=r3&type=uitspraak&"
)
RECHTSPRAAK_METADATA_API_BASE_URL = "http://data.rechtspraak.nl/uitspraken/content?id="
return_type = "&return=DOC"


# Check whether the API is working or not and return with the response code
def check_api(url):
    response = requests.get(f"{url}")
    return response.status_code


# It also only grabs data if it has rechtspraak in it
# As that was causing issues with other csv data present
def read_csv(dir_name, exclude=None):
    path = dir_name
    csv_files = glob.glob(path + "/*.csv")
    files = []
    for i in csv_files:
        if exclude is not None:
            if exclude not in i and "rechtspraak" in i:
                files.append(i)
        else:
            if "rechtspraak" in i:
                files.append(i)
    # print("Found " + str(len(files)) + " CSV file(s)\n")
    return files


# Get total execution time
def get_exe_time(start_time):
    end_time = time.time()
    sec = end_time - start_time
    mins = sec // 60
    sec = sec % 60
    hours = mins // 60
    mins = mins % 60
    # print(
    #     "Total execution time: {0}:{1}:{2}".format(int(hours), int(mins), round(sec, 2))
    # )
    # print("\n")


def get_data_from_url(url):
    res = requests.get(url)
    # print(url)
    res.raw.decode_content = True

    # Convert the XML data to JSON format
    xpars = xmltodict.parse(res.text)
    json_string = json.dumps(xpars)
    json_object = json.loads(json_string)

    # Get the JSON object from a specific branch
    json_object = json_object["feed"]["entry"]

    return json_object


def save_csv(json_object, file_name, save_file):
    df = pd.DataFrame(columns=["id", "title", "summary", "updated", "link"])
    ecli_id = []
    title = []
    summary = []
    updated = []
    link = []

    for i in json_object:
        ecli_id.append(i["id"])
        title.append(i["title"]["#text"])
        if "#text" in i["summary"]:
            summary.append(i["summary"]["#text"])
        else:
            summary.append("No summary available")
        updated.append(i["updated"])
        link.append(i["link"]["@href"])

    df["id"] = ecli_id
    df["title"] = title
    df["summary"] = summary
    df["updated"] = updated
    df["link"] = link

    if save_file == "y":
        Path("data").mkdir(parents=True, exist_ok=True)
        df.to_csv("data/" + file_name + ".csv", index=False, encoding="utf8")
        # print("Data saved to CSV file successfully.")
    return df


def get_rechtspraak(max_ecli=100, sd="1900-01-01", ed=None, save_file="y"):
    amount = max_ecli
    starting_date = sd
    save_file = save_file

    # If the end date is not entered, the current date is taken
    today = date.today()
    if ed:
        ending_date = ed
    else:
        ending_date = today.strftime("%Y-%m-%d")

    # Used to calculate total execution time
    start_time = time.time()

    # Build the URL after getting all the arguments
    url = (
        RECHTSPRAAK_API_BASE_URL
        + "max="
        + str(amount)
        + "&date="
        + starting_date
        + "&date="
        + ending_date
    )

    response_code = check_api(url)
    if response_code == 200:
        # print("API is working fine!")
        # print(
        #     f"Getting {str(amount)} documents from {starting_date} till {ending_date}"
        # )

        json_object = get_data_from_url(url)
        print(f"Found {len(json_object)} cases!")
        if json_object:
            current_time = datetime.now().strftime("%H-%M-%S")
            file_name = f"rechtspraak_{starting_date}_{ending_date}_{current_time}"

            get_exe_time(start_time)

            if save_file == "n":
                global_rs_df = save_csv(json_object, file_name, save_file)
                return global_rs_df
            else:
                save_csv(json_object, file_name, save_file)
                return
    else:
        print(f"URL returned with a {response_code} error code")


def get_cores():
    # max_workers is the number of concurrent processes supported by your CPU multiplied by 5.
    # You can change it as per the computing power.
    # Different python versions treat this differently. This is written as per python 3.6.
    n_cores = multiprocessing.cpu_count()

    global max_workers
    max_workers = n_cores - 1
    # If the main process is computationally intensive: Set to the number of logical CPU cores minus one.

    # print(f"Maximum {max_workers} threads supported by your machine.")


def extract_data_from_xml(url):
    with urllib.request.urlopen(url) as response:
        xml_file = response.read()
        return xml_file


def check_if_df_empty(df):
    if df.empty:
        return True
    return False


def get_text_if_exists(el):
    try:
        return el.text
    except Exception as e:
        return ""


def update_bar(bar, *args):
    bar.update(1)


def save_data_when_crashed(ecli):
    ecli_df.append(ecli)
    full_text_df.append("")
    creator_df.append("")
    date_decision_df.append("")
    issued_df.append("")
    zaaknummer_df.append("")
    type_df.append("")
    relations_df.append("")
    references_df.append("")
    subject_df.append("")
    procedure_df.append("")
    inhoudsindicatie_df.append("")
    hasVersion_df.append("")


def get_data_from_api(ecli_id):
    url = RECHTSPRAAK_METADATA_API_BASE_URL + ecli_id + return_type
    response_code = check_api(url)

    global ecli_df, full_text_df, creator_df, date_decision_df, issued_df, zaaknummer_df
    global type_df, relations_df, references_df, subject_df, procedure_df, inhoudsindicatie_df, hasVersion_df

    if response_code == 200:
        # print(f"responsecode {url}: {response_code}")
        # Extract data from xml
        xml_object = extract_data_from_xml(url)
        soup = BeautifulSoup(xml_object, features="xml")
        # Get the data
        creator = get_text_if_exists(soup.find("dcterms:creator"))
        date_decision = get_text_if_exists(soup.find("dcterms:date"))
        issued = get_text_if_exists(soup.find("dcterms:issued"))
        zaaknummer = get_text_if_exists(soup.find("psi:zaaknummer"))
        rs_type = get_text_if_exists(soup.find("dcterms:type"))
        subject = get_text_if_exists(soup.find("dcterms:subject"))
        relation = soup.findAll("dcterms:relation")
        relatie = ""
        for i in relation:
            # append the string to relation
            text = get_text_if_exists(i)
            if text == "":
                continue
            else:
                relatie += text + "\n"
        relations = relatie
        reference = soup.findAll("dcterms:references")
        ref = ""
        for u in reference:
            text = get_text_if_exists(u)
            if text == "":
                continue
            else:
                ref += text + "\n"
        references = ref
        procedure = get_text_if_exists(soup.find("psi:procedure"))
        inhoudsindicatie = get_text_if_exists(soup.find("inhoudsindicatie"))
        hasVersion = get_text_if_exists(soup.find("dcterms:hasVersion"))
        full_text = get_text_if_exists(soup.find("uitspraak"))

        # only add inbraak cases
        if (
            # "inbraak" in inhoudsindicatie.lower()
            # or "diefstal" in inhoudsindicatie.lower()
            # or "inbraak" in full_text.lower()
            # or "diefstal" in full_text.lower()
            len(full_text)
            > 20
        ):
            ecli_df.append(ecli_id)
            full_text_df.append(full_text)
            creator_df.append(creator)
            date_decision_df.append(date_decision)
            issued_df.append(issued)
            zaaknummer_df.append(zaaknummer)
            type_df.append(rs_type)
            relations_df.append(relations)
            references_df.append(references)
            subject_df.append(subject)
            procedure_df.append(procedure)
            inhoudsindicatie_df.append(inhoudsindicatie)
            hasVersion_df.append(hasVersion)
        del (
            full_text,
            creator,
            date_decision,
            issued,
            zaaknummer,
            relations,
            rs_type,
            references,
            subject,
            procedure,
            inhoudsindicatie,
            hasVersion,
        )
        urllib.request.urlcleanup()


def get_rechtspraak_metadata(save_file="n", dataframe=None, filename=None):
    if dataframe is not None and filename is not None:
        # print("Please provide either a dataframe or a filename, but not both")
        return False

    if dataframe is None and filename is None and save_file == "n":
        # print(
        #     'Please provide at least a dataframe of filename when the save_file is "n"'
        # )
        return False

    # print("Rechtspraak metadata API")

    start_time = time.time()  # Get start time

    no_of_rows = ""
    rs_data = ""

    # Check if dataframe is provided and is correct
    if dataframe is not None:
        if "id" in dataframe and "link" in dataframe:
            rs_data = dataframe
            no_of_rows = rs_data.shape[0]
        else:
            # print(
            #     "Dataframe is corrupted or does not contain necessary information to get the metadata."
            # )
            return False

    get_cores()  # Get number of cores supported by the CPU

    if rs_data is not None:
        rsm_df = pd.DataFrame(
            columns=[
                "ecli",
                "full_text",
                "creator",
                "date_decision",
                "issued",
                "zaaknummer",
                "type",
                "relations",
                "references",
                "subject",
                "procedure",
                "inhoudsindicatie",
                "hasVersion",
            ]
        )

        # print("Getting metadata of " + str(no_of_rows) + " ECLIs")
        # print("Working. Please wait...")
        # Get all ECLIs in a list
        ecli_list = list(rs_data.loc[:, "id"])

        # Create a temporary directory to save files
        Path("temp_rs_data").mkdir(parents=True, exist_ok=True)
        time.sleep(1)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            bar = tqdm(
                total=len(ecli_list),
                colour="GREEN",
                position=0,
                leave=True,
                miniters=int(len(ecli_list) / 100),
                maxinterval=10000,
            )
            for ecli in ecli_list:
                threads.append(executor.submit(get_data_from_api, ecli))
            for t in threads:
                t.add_done_callback(partial(update_bar, bar))

        shutil.rmtree("temp_rs_data")

        global ecli_df, full_text_df, creator_df, date_decision_df, issued_df, zaaknummer_df, type_df
        global relations_df, references_df, subject_df, procedure_df, inhoudsindicatie_df, hasVersion_df
        print(f"Number of cases with metadata: {len(ecli_df)}")
        rsm_df["ecli"] = ecli_df
        rsm_df["full_text"] = full_text_df
        rsm_df["creator"] = creator_df
        rsm_df["date_decision"] = date_decision_df
        rsm_df["issued"] = issued_df
        rsm_df["zaaknummer"] = zaaknummer_df
        rsm_df["type"] = type_df
        rsm_df["relations"] = relations_df
        rsm_df["references"] = references_df
        rsm_df["subject"] = subject_df
        rsm_df["procedure"] = procedure_df
        rsm_df["inhoudsindicatie"] = inhoudsindicatie_df
        rsm_df["hasVersion"] = hasVersion_df
        addition = rs_data[["id", "summary"]]
        rsm_df = rsm_df.merge(addition, how="left", left_on="ecli", right_on="id").drop(
            ["id"], axis=1
        )

        # Clear the lists for the next file
        ecli_df = []
        full_text_df = []
        creator_df = []
        date_decision_df = []
        issued_df = []
        zaaknummer_df = []
        type_df = []
        relations_df = []
        references_df = []
        subject_df = []
        procedure_df = []
        inhoudsindicatie_df = []
        hasVersion_df = []
        ecli_list = []

        get_exe_time(start_time)

        if save_file == "n":
            return rsm_df

        return True
