import json
import logging
import os
import uuid
import io

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from requests import HTTPError
from swiftclient.service import (
    ClientException,
    SwiftError,
    SwiftService,
    SwiftUploadObject,
)

from dittydally import DittyDallyMusicClient

load_dotenv()

app = Flask(__name__)
CORS(app, origins=["https://dittydally.com", "http://localhost:4321"])

MUSIC_ENDPOINT = os.environ.get("DITTYDALLY_MUSIC_ENDPOINT")
dally = DittyDallyMusicClient(MUSIC_ENDPOINT)

logging.basicConfig(level=logging.INFO)


@app.route("/")
def index():
    return "dittydally poster catalog"


# list all album containers with their base_data
@app.route("/albums", methods=["GET"])
def list_album_containers():
    with SwiftService() as swift:
        app.logger.info("listing catalog album containers")

        container_album_mapping = {}

        # list calls return iterator of pages, pages have a listing of objects
        container_pages = swift.list()

        for page in container_pages:
            if not page["success"]:
                app.logger.error("Failed to fetch container list")
                return jsonify({"error": "Failed to fetch container list"}), 500

            for container in page["listing"]:
                # album ID here
                container_name = container["name"]

                for result_obj in swift.download(
                    container_name, ["base_data.json"], options={"out_file": "-"}
                ):
                    if result_obj["contents"]:
                        reader = result_obj["contents"]
                        json_data = swift_results_to_JSON(reader)
                        container_album_mapping[container_name] = json_data
                    else:
                        app.logger.info(f"{result_obj['object']} failed to download")

        return jsonify({"container : album": container_album_mapping})


# get album config by UUID
@app.route("/albums/<album_id>/<config_id>", methods=["GET"])
def get_album_config(album_id, config_id):
    with SwiftService() as swift:
        app.logger.info(f"Fetching config '{config_id}' for album '{album_id}'")

        try:
            downloaded_config_pages = swift.download(
                album_id, [f"{config_id}.json"], options={"out_file": "-"}
            )

            for result_obj in downloaded_config_pages:
                if "contents" in result_obj:
                    reader = result_obj["contents"]
                    json_data = swift_results_to_JSON(reader)

                    return {"album_config": json_data}
                else:
                    app.logger.error(
                        f"Config '{config_id}' for album '{album_id}' doesn't exist."
                    )

                    return jsonify(
                        {
                            "error": f"Config '{config_id}' for album '{album_id}' not found."
                        }
                    ), 404
        except (ClientException, SwiftError) as e:
            app.logger.error(
                f"Exception while fetching config '{config_id}' for album '{album_id}' message: '{e.value}'."
            )

            return jsonify(
                {
                    "error": f"Failed to fetch config '{config_id}' for album '{album_id}'"
                }
            ), 500


# get basedata for an album
@app.route("/albums/<album_id>/base_data", methods=["GET"])
def get_album_basedata(album_id):
    with SwiftService() as swift:
        app.logger.info(f"Fetching base data for album with ID '{album_id}'")

        try:
            album_container_results = swift.download(
                album_id, ["base_data.json"], options={"out_file": "-"}
            )

            for down_res in album_container_results:
                if down_res["contents"]:
                    reader = down_res["contents"]
                    result_obj = swift_results_to_JSON(reader)

                    return {"base_data": result_obj}
                else:
                    app.logger.error(f"{down_res['object']} failed to download")

                    return jsonify(
                        {"error": f"Failed to fetch base data for album '{album_id}'"}
                    ), 500
        except (ClientException, SwiftError) as e:
            app.logger.error(
                f"Exception while fetching base data for album '{album_id}' message: '{e.value}'."
            )

            return jsonify(
                {"error": f"Failed to fetch base data for album '{album_id}'"}
            ), 500


# list of album configs
@app.route("/albums/<album_id>/configs", methods=["GET"])
def list_album_configs(album_id):
    with SwiftService() as swift:
        app.logger.info(f"listing configs for album with ID '{album_id}'")

        try:
            album_catalog_content = swift.list(container=album_id)

            for page in album_catalog_content:
                if not page["success"]:
                    return jsonify(
                        {"error": f"Failed to fetch album configs, ID: '{album_id}"}
                    ), 500

                # we want all items that aren't base_data
                configs = []
                for item in page["listing"]:
                    if "base_data.json" in item["name"]:
                        continue

                    downloaded_config = swift.download(
                        album_id, [item["name"]], options={"out_file": "-"}
                    )

                    for result_obj in downloaded_config:
                        if result_obj["contents"]:
                            reader = result_obj["contents"]
                            result_obj = swift_results_to_JSON(reader)
                            configs.append(result_obj)
                        else:
                            app.logger.error(
                                f"{result_obj['object']} failed to download"
                            )

                return jsonify({"configs": configs})
        except (ClientException, SwiftError) as e:
            app.logger.error(
                f"Exception while listing configs for album '{album_id}' message: '{e.value}'."
            )
            return jsonify(
                {"error": f"Failed to fetch album configs, ID: '{album_id}'"}
            ), 500


# add a new config for a poster under a container named album id
@app.route("/albums/<album_id>", methods=["POST"])
def add_album_config(album_id):
    config_data = request.get_json()

    if "dally_config" not in config_data:
        return jsonify({"error": "Missing 'dally_config' in request"}), 400

    with SwiftService() as swift:
        album = None

        try:
            # load album data from spotify
            album = dally.get_spotify_album_by_id(album_id)
        except (HTTPError, ValueError) as e:
            app.logger.error(
                f"Failed to fetch album data for album with ID '{album_id}'. Cause: {e}"
            )

            return jsonify(
                {
                    "error": f"Failed to fetch album data for album with ID '{album_id}'. Cause: {e.strerror}"
                }
            ), 404

        # check if we already have a container for this album
        newContainer = False

        try:
            result = swift.list(container=album_id)
            for res in result:
                if not res["success"]:
                    newContainer = True
        except (ClientException, SwiftError) as e:
            # swift.list actually doesn't seem to raise a SwiftError when listing an
            # empty container despite what the docs say, this is for posterity really
            app.logger.error(
                f"Exception while checking for album container '{album_id}' message: '{e.value}'."
            )

        # create container w/basedata
        if newContainer:
            app.logger.info(f"Creating catalog container for album '{album_id}'")

            container_creation_result = create_album_container_with_basedata(
                swift, album
            )

            if container_creation_result:
                app.logger.info(
                    f"Successfully created catalog container for album '{album.title()}' with ID '{album_id}'"
                )
            else:
                app.logger.error(
                    f"Failed to create catalog container for album '{album.title()}' with ID '{album_id}'"
                )
                return jsonify(
                    {
                        "error": f"Failed to create catalog container for album '{album.title()}' with ID '{album_id}'"
                    }
                ), 500

        # upload new poster config
        config_upload_results = upload_album_config(
            swift, album, config_data["dally_config"]
        )

        if config_upload_results:
            return jsonify(
                {
                    "id": config_upload_results,
                    "message": f"Config '{config_upload_results}' for album '{album.title()}' created successfully",
                }
            )
        else:
            return jsonify(
                {
                    "error": f"Failed to upload config for album '{album.title()}' with ID '{album_id}'"
                }
            ), 500


def swift_results_to_JSON(reader):
    # When downloading objects, I didn't want to save them locally to disk.
    # By setting out_file to "-",  you can get a SwiftReader thing that lets
    # you read bits in and convert that to JSON in memory
    # read as bytes using swiftreader
    data_bytes = b"".join(chunk for chunk in reader)
    json_str = data_bytes.decode("utf-8")
    return json.loads(json_str)


def create_album_container_with_basedata(swift_service, album):
    base_data = json.dumps(
        {
            "id": album.id(),
            "title": album.title(),
            "artists": album.artists(),
        }
    )

    # in mem IO object to upload
    json_string = json.dumps(base_data)
    temp_readable = io.StringIO(json_string)
    upload_object = SwiftUploadObject(
        source=temp_readable,
        object_name="base_data.json",
        options={"content_type": "application/json"},
    )

    try:
        upload_result = swift_service.upload(
            container=album.id(),
            objects=[upload_object],
        )

        for result in upload_result:
            if result["success"]:
                app.logger.info(f"Uploaded base_data.json for album '{album.title()}'.")
                return True
            else:
                app.logger.error(
                    f"Failed to upload base_data.json for album '{album.title()}'."
                )
    except SwiftError as e:
        app.logger.error(f"Failed to upload base_data.json: {e.value}")

    return False


def upload_album_config(swift_service, album, config):
    album_id = album.id()
    config_id = str(uuid.uuid4())[:8]

    # add id to config for self-reference later
    config["configId"] = config_id

    # in mem IO object to upload
    json_string = json.dumps(config)
    temp_readable = io.StringIO(json_string)
    upload_object = SwiftUploadObject(
        source=temp_readable,
        object_name=f"{config_id}.json",
        options={"content_type": "application/json"},
    )

    try:
        for results in swift_service.upload(
            container=album_id,
            objects=[upload_object],
        ):
            if results["success"]:
                app.logger.info(
                    f"Uploaded config {config_id} for album '{album.title()}'."
                )
                return f"{config_id}"
    except SwiftError as e:
        app.logger.error(f"Failed to upload base_data.json: {e.value}")

    app.logger.error(
        f"Failed to upload config {config_id} for album '{album.title()}'."
    )

    return False


if __name__ == "__main__":
    app.run()
