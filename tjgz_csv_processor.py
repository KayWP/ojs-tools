import argparse
import datetime
import os
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, ElementTree

import numpy as np
from pandas import DataFrame

from output_csv_validator import validate_csv


def add_authors(metadata: ElementTree, row: dict):
    authors = metadata.findall(".//contrib[@contrib-type='author']")
    author_count = 0

    for author in authors:
        given_name_field = f"author_given_name_{author_count}"
        family_name_field = f"author_family_name_{author_count}"
        affiliation_field = f"author_affiliation_{author_count}"

        author_names = author.find(".//name")
        if author_names is not None and len(author_names) > 0:
            for name in author_names:
                if name.tag == "given-names":
                    row[given_name_field] = name.text

                if name.tag == "surname":
                    row[family_name_field] = name.text
        person_affiliation = author.find(".//xref[@ref-type='aff']")
        if person_affiliation is not None:
            affiliation_id = person_affiliation.attrib["rid"]
            affiliation = metadata.find(f".//aff[@id='{affiliation_id}']")

            division = affiliation.find(".//institution[@content-type='org-division']")
            org_name = affiliation.find(".//institution[@content-type='org-name']")
            if division is not None and org_name is not None:
                affiliation_data = f"{division.text}, {org_name.text}"
                row[affiliation_field] = affiliation_data

        author_count += 1

    if "author_given_name_0" not in row.keys():
        row[f"author_given_name_0"] = "Onbekend"


def process_file(metadata_file: str, metadata_file_parent: str, document_parent: str, row: dict):
    metadata = ET.parse(os.path.join(metadata_file_parent, metadata_file))

    row["title"] = metadata.find(".//title-group/article-title").text
    row["file"] = os.path.join(document_parent, metadata_file.replace("_nlm.xml.Meta", ".pdf"))
    row["doi"] = metadata.find(".//article-id[@pub-id-type='doi']").text
    year_element = metadata.find(".//pub-date[@publication-format='print']/year")
    month_element = metadata.find(".//pub-date[@publication-format='print']/month")

    if year_element is None:
        year_element = metadata.find(".//pub-date[@date-type='ppub']/year")
        month_element = metadata.find(".//pub-date[@date-type='ppub']/month")

    row["year"] = int(year_element.text)
    row["volume"] = int(metadata.find(".//volume").text)
    row["issue"] = metadata.find(".//issue").text
    row["publication"] = f"{row['year']} / {row['issue']}"
    year = int(year_element.text)
    month = int(month_element.text)
    day = 1
    date = datetime.date(year, month, day)
    row["publication_date"] = date.strftime("%Y-%m-%d")
    fpage = metadata.find(".//fpage").text
    row["from_page"] = int(fpage)
    lpage = metadata.find(".//lpage").text
    row["page_number"] = f"{fpage}-{lpage}"
    section = metadata.find(".//subj-group[@subj-group-type='heading']/subject").text
    row["section_title"] = section
    row["section_policy"] = "standard"
    row["section_reference"] = section

    abstract = metadata.find(".//abstract")
    add_abstract(abstract, row)

    add_authors(metadata, row)


def add_abstract(abstract: Element, row: dict):
    if abstract is not None:
        abstract_lines = []

        for line in abstract:
            text = ET.tostring(line, encoding='utf-8', method='text').decode("utf-8")
            if text is not None:
                abstract_lines.append(text)

        row["abstract"] = "\n".join(abstract_lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata_path", required=True)
    parser.add_argument("--files_path", required=True)
    parser.add_argument("--output_csv", required=True)
    args = parser.parse_args()

    xml_path = args.metadata_path
    files_path = args.files_path

    data = DataFrame()
    data.insert(0, "title", np.nan)
    data.insert(len(data.columns), "abstract", np.nan)
    data.insert(len(data.columns), "file", np.nan)
    data.insert(len(data.columns), "year", np.nan)
    data.insert(len(data.columns), "volume", np.nan)
    data.insert(len(data.columns), "issue", np.nan)
    data.insert(len(data.columns), "publication", np.nan)
    data.insert(len(data.columns), "publication_date", np.nan)
    data.insert(len(data.columns), "page_number", np.nan)
    data.insert(len(data.columns), "section_title", np.nan)
    data.insert(len(data.columns), "section_policy", np.nan)
    data.insert(len(data.columns), "section_reference", np.nan)
    data.insert(len(data.columns), "from_page", np.nan)
    data.insert(len(data.columns), "doi", np.nan)
    for root, dirs, files in os.walk(xml_path):
        print(root)
        for file in files:
            row = {}
            print(file)
            process_file(file, root, files_path, row)
            for key in row.keys():
                if key not in data.columns:
                    data.insert(len(data.columns), key, np.nan)
            data.loc[len(data)] = row

    data = data.sort_values(["year", "issue", "from_page"])
    data.insert(0, 'id', np.arange(1, len(data) + 1))
    data.drop(["from_page"], axis=1)
    validate_csv(data)
    data.to_csv(args.output_csv, sep=";", index=False)
