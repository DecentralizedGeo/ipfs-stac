# Standard Library Imports
import os
import json
from io import StringIO, BytesIO
from pathlib import Path
from typing import Callable, List, Optional, Sequence
import warnings
from typing import Union, Iterator, Any
import subprocess
import atexit

# Third Party Imports
import fsspec
import requests
import pandas as pd
from bs4 import BeautifulSoup
from pystac_client import Client, CollectionClient
from pystac import Collection, Item, ItemCollection
import numpy as np
import rasterio
from yaspin import yaspin
import psutil


# Global Variables
ENV_VAR_NAME = "IPFS_GATEWAY"
REMOTE_GATEWAYS = [
    "https://ipfs.io",
    "https://cloudflare-ipfs.com",
    "https://dweb.link",
]


def ensure_data_fetched(func) -> Callable[..., Any]:
    def wrapper(self, *args, **kwargs) -> Any:
        if self.data is None:
            print("Data for asset has not been fetched yet. Fetching now...")
            self.fetch()
        return func(self, *args, **kwargs)

    return wrapper


def fetchCID(cid: str) -> bytes:
    """
    Fetches data from CID.

    Args:
        cid (str): CID to retrieve.

    Returns:
        bytes: Retrieved data.
    """
    try:
        fs = fsspec.filesystem("ipfs")
        progress = 0

        with fs.open(f"ipfs://{cid}", "rb") as contents:
            total_size = fs.size(f"ipfs://{cid}")
            with yaspin(
                text=f"Fetching {cid.split('/')[-1]} - {progress / 1048576:.2f}/{fs.size(f'ipfs://{cid}') / 1048576:.2f} MB",
                color=None,
            ) as spinner:
                file_data = bytearray()

                while True:
                    chunk = contents.read()
                    if not chunk:
                        break
                    file_data.extend(chunk)
                    progress += len(chunk)
                    spinner.text = f"Fetching {cid.split('/')[-1]} - {progress / 1048576:.2f}/{total_size / 1048576:.2f} MB"

            if file_data:
                spinner.ok("✅ ")
            else:
                spinner.fail("💥 ")

            return bytes(file_data)
    except FileNotFoundError as e:
        print(f"Could not file with CID: {cid}. Are you sure it exists?")
        raise e


class Web3:
    def __init__(
        self,
        local_gateway: str = "localhost",
        api_port: int = 5001,
        gateway_port: int = 8080,
        stac_endpoint: str = "https://stac.easierdata.info",
    ) -> None:
        """
        Web3 client constructor.

        Args:
            local_gateway (str): Local gateway endpoint without port. Defaults to "localhost".
            api_port (int): API port. Defaults to 5001.
            gateway_port (int): Gateway port. Defaults to 8080.
            stac_endpoint (str): STAC browser endpoint. Defaults to "https://stac.easierdata.info".
        """
        self.local_gateway = local_gateway
        self.stac_endpoint = stac_endpoint
        self.daemon_status = None
        self.client: Client = Client.open(self.stac_endpoint)
        self.collections: List[str] = self._get_collections_ids()
        self.config = None

        self.api_port = api_port
        self.gateway_port = gateway_port

        if self.local_gateway:
            self.startDaemon()

        # When local gateway is `localhost``, ipfsspec does not play well with it.
        # This is a workaround to set the environment variable to the local gateway as `127.0.0.1`
        if self.local_gateway == "localhost":
            os.environ[ENV_VAR_NAME] = f"http://127.0.0.1:{self.gateway_port}"

        # Load configuration at instantiation
        # config_path = os.path.join(os.path.dirname(__file__), "config.json")
        # with open(config_path, "r") as f:
        #     self.config = json.load(f)

    def overwrite_config(self, path: Optional[Path] = None) -> None:
        """
        Overwrite configuration file with configuration in memory.

        Args:
            path (Optional[Path]): Path to configuration file (optional).
        """

        # Get user's home directory
        home = Path.home()
        if path:
            config_path = path
        else:
            config_path = Path(home, ".ipfs", "config")

        with Path.open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f)

    def _get_collections_ids(self) -> List[str]:
        """
        Get the collection ids from the STAC endpoint.

        Returns:
            List[str]: List of collection ids.
        """
        return [collection.id for collection in self.client.get_collections()]

    def getCollections(self) -> Sequence[Collection]:
        """
        Returns list of collections from STAC endpoint.

        Returns:
            Sequence[Collection]: List of collections.
        """
        return list(self.client.get_collections())

    def _is_process_running(self) -> bool:
        """
        Check if IPFS daemon process is running.

        Returns:
            bool: True if process is running, False otherwise.
        """
        process_name = "ipfs"
        for proc in psutil.process_iter(["name"]):
            try:
                if process_name.lower() in proc.info["name"].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    def shutdown_process(self) -> None:
        """
        Shutdown the IPFS daemon process.
        """
        if self.daemon_status:
            print("Shutdown process is running...")

            self.daemon_status.terminate()
            self.daemon_status.wait(timeout=3)

            # If process is still running, kill it
            if self._is_process_running():
                self.daemon_status.kill()

            # If process is still running, exit with error
            elif self._is_process_running():
                import sys

                sys.exit("Failed to shutdown IPFS daemon")

            self.daemon_status = None

    def startDaemon(self) -> None:
        """
        Start the IPFS daemon process.

        Raises:
            Exception: If the IPFS daemon fails to start.
        """
        try:
            if not self._is_process_running():
                self.daemon_status = subprocess.Popen(["ipfs", "daemon"])
                atexit.register(self.shutdown_process)

            heartbeat_response = requests.post(
                f"http://{self.local_gateway}:{self.api_port}/api/v0/id",
                timeout=10,
            )
            if heartbeat_response.status_code != 200:
                warnings.warn(
                    "IPFS Daemon is running but still can't connect. Check your IPFS configuration."
                )
        except Exception as exc:
            print(f"Error starting IPFS daemon: {exc}")
            raise Exception("Failed to start IPFS daemon")

    def getFromCID(self, cid: str) -> Union[bytes, None]:
        """
        Retrieves raw data from CID.

        Args:
            cid (str): CID to retrieve.

        Returns:
            Union[bytes, None]: Retrieved data or None if not found.
        """
        content_cid = None
        try:
            content_cid = fetchCID(cid)
        except FileNotFoundError as e:
            print(f"Could not file with CID: {cid}. Are you sure it exists?")
            raise e
        return content_cid

    def searchSTACByBox(
        self, bbox: List[float], collections: List[str]
    ) -> ItemCollection:
        """
        Search STAC catalog by bounding box and return array of items.

        Args:
            bbox (List[float]): Array of coordinates for bounding box.
            collections (List[str]): Array of collection names.

        Returns:
            ItemCollection: Collection of items.
        """
        catalog = Client.open(self.stac_endpoint)
        search_results = catalog.search(
            collections=collections,
            bbox=bbox,
        )

        return search_results.item_collection()

    def searchSTAC(self, **kwargs) -> ItemCollection:
        """
        Search STAC catalog for items using the search method from pystac-client.

        Note: No request is sent to the API until a method is called to iterate
        through the resulting STAC Items, either :meth:`ItemSearch.item_collections`,
        :meth:`ItemSearch.items`, or :meth:`ItemSearch.items_as_dicts`.

        Args:
            kwargs: Keyword arguments for the search method.

        Returns:
            ItemCollection: List of pystac.Item objects.
        """
        try:
            search_results = self.client.search(**kwargs)
            return search_results.item_collection()

        except Exception as e:
            # Print the error message and the keyword argument that caused the error.
            if isinstance(e, TypeError):
                print(f"Error: {e}")
                print(f"Search method docstring: {self.client.search.__doc__}")
            else:
                print(f"Error: {e}")
            return ItemCollection([])

    def searchSTACByBoxIndex(
        self, bbox: List[float], collections: List[str], index: int
    ) -> Item:
        """
        Search STAC catalog by bounding box and return singular item.

        Args:
            bbox (List[float]): Array of coordinates for bounding box.
            collections (List[str]): Array of collection names.
            index (int): Index of item to return.

        Returns:
            Item: STAC item.
        """
        # Validate Bounding box coordinates before trying to search
        if (
            not isinstance(bbox, list)
            or len(bbox) != 4
            or not all(isinstance(coord, float) for coord in bbox)
        ):
            raise ValueError("bbox must be a list of four float numbers")

        catalog = Client.open(self.stac_endpoint)
        search_results = catalog.search(
            collections=collections,
            bbox=bbox,
        )

        return search_results.item_collection()[index]

    def getAssetNames(
        self, stac_obj: Union[CollectionClient, ItemCollection, Item]
    ) -> Union[List[str], None]:
        """
        Get a list of unique asset names from a STAC object.

        Args:
            stac_obj (Union[CollectionClient, ItemCollection, Item]): STAC object to get asset names from.

        Returns:
            Union[List[str], None]: A sorted list of unique asset names.
        """

        def get_asset_names_from_items(items: List[Item]) -> List[str]:
            """
            Get asset names from list of items.

            Args:
                items (List[Item]): List of STAC item objects.

            Returns:
                List[str]: A sorted list of unique asset names.
            """
            asset_names = set()
            for item in items:
                names = list(item.get_assets().keys())
                asset_names.update(names)
            return sorted(asset_names)

        if not stac_obj:
            raise ValueError(
                "STAC Object (CollectionClient, ItemCollection, Item) must be provided"
            )

        if isinstance(stac_obj, CollectionClient):
            try:
                items = stac_obj.get_items()
                return get_asset_names_from_items(list(items))
            except Exception as e:
                print(f"Error with getting asset names: {e}")
        elif isinstance(stac_obj, ItemCollection):
            try:
                items = stac_obj.items
                return get_asset_names_from_items(list(items))
            except Exception as e:
                print(f"Error with getting asset names: {e}")
        elif isinstance(stac_obj, Item):
            try:
                return sorted(stac_obj.get_assets().keys())
            except Exception as e:
                print(f"Error with getting asset names: {e}")
        else:
            raise ValueError(
                "STAC Object must be a Collection, Item, or ItemCollection"
            )

    def getAssetFromItem(
        self, item: Item, asset_name: str, fetch_data: bool = False
    ) -> Union["Asset", None]:
        """
        Returns asset object from item.

        Args:
            item (Item): STAC catalog item.
            asset_name (str): Name of asset to return.
            fetch_data (bool, optional): Fetch data from CID. Defaults to False.

        Returns:
            Union[Asset, None]: Asset object.
        """
        try:
            item_dict = item.to_dict()
            cid = item_dict["assets"][f"{asset_name}"]["alternate"]["IPFS"][
                "href"
            ].split("/")[-1]
            return Asset(
                cid,
                self.local_gateway,
                self.api_port,
                fetch_data=fetch_data,
                name=asset_name,
            )
        except Exception as e:
            print(f"Error with getting asset: {e}")

    def getAssetsFromItem(
        self, item: Item, assets: List[str]
    ) -> Union[List["Asset"], None]:
        """
        Returns array of asset objects from item.

        Args:
            item (Item): STAC catalog item.
            assets (List[str]): Names of asset to return (strings).

        Returns:
            Union[List[Asset], None]: List of asset objects.
        """
        try:
            assetArray = []

            for i in assets:
                assetArray.append(self.getAssetFromItem(item, i, fetch_data=False))

            return assetArray
        except Exception as e:
            print(f"Error with getting assets: {e}")

    def writeCID(self, cid: str, filePath: Union[str, Path]) -> None:
        """
        Write CID contents to local file system (WIP).

        Args:
            cid (str): CID to retrieve.
            filePath (Union[str, Path]): Directory to write contents to.
        """
        try:
            # Check filepath instance and convert to Path object if necessary
            if isinstance(filePath, str):
                filePath = Path(filePath).resolve()
            else:
                filePath = filePath.resolve()
            data_payload = bytes()
            with fsspec.open(f"ipfs://{cid}", "rb") as contents:
                data_payload = contents.read()
                # Write data to local file path
            with filePath.open("wb") as copy:
                copy.write(data_payload)
        except Exception as e:
            print(f"Error with CID write: {e}")

    def uploadToIPFS(
        self,
        content: Union[str, Path, bytes],
        file_name: Optional[str] = None,
        pin_content: bool = False,
        mfs_path: Optional[str] = None,
        chunker: Optional[str] = None,
    ) -> None:
        """
        Uploads a file or bytes data to IPFS.

        Args:
            content (Union[str, Path, bytes]): The path to the file or bytes data to be uploaded.
            file_name (Optional[str]): The name of the file. Defaults to None.
            pin_content (bool): Pin locally to protect added files from garbage collection. Defaults to False.
            mfs_path (Optional[str]): Add reference to Files API (MFS) at the provided path. Defaults to None.
            chunker (Optional[str]): Chunking algorithm, size-[bytes], rabin-[min]-[avg]-[max] or buzhash. Defaults to None.

        Raises:
            ValueError: If neither `file_path` nor `bytes_data` is provided.
            ValueError: If `bytes_data` is not of type bytes.
            FileNotFoundError: If the file path provided does not exist.

        Returns:
            str: The CID (Content Identifier) of the uploaded content.
        """

        # Setting param options
        param_options = f"cid-version=1&pin={pin_content}"
        if mfs_path:
            param_options = f"{param_options}&to-files={mfs_path}"
        if chunker:
            param_options = f"{param_options}&chunker={chunker}"

        # Define empty payload dictionary
        components = {"content": b"", "name": None}

        # Check the type of content and handle accordingly
        if isinstance(content, bytes):
            components["content"] = content
            if not file_name:
                components["name"] = None
        elif isinstance(content, (str, Path)):
            file_path = Path(content).resolve()
            if file_path.exists():
                with Path.open(file_path) as f:
                    components["content"] = f.read()
                    components["name"] = file_path.name
                # Override the file name if user provides one
                if file_name:
                    components["name"] = file_name
            else:
                raise FileNotFoundError(
                    f"The file path provided does not exist. Please check {content}"
                )
        else:
            raise ValueError("`content` must be of type `Union[str, Path, bytes]`.")

        # put the components together as a file payload
        if components["name"] is not None:
            file_payload = {"file": (components["name"], components["content"])}
        else:
            file_payload = {"file": components["content"]}

        try:
            response = requests.post(
                f"http://{self.local_gateway}:{self.api_port}/api/v0/add?{param_options}",
                files=file_payload,
                timeout=10,
            )
            response.raise_for_status()  # Raise an exception for HTTP errors

            # response.raise_for_status()  # Raise an exception for HTTP errors
            if response.status_code == 200:
                data = response.json()
                print(
                    f"Successfully added, {data['Name']}, to IPFS. CID: {data['Hash']}"
                )
                print(
                    f"Click here to view: http://{data['Hash']}.ipfs.{self.local_gateway}:{self.gateway_port}"
                )
                return data["Hash"]

        except requests.exceptions.Timeout:
            print("The request timed out")
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")

    def pinned_list(
        self, pin_type: str = "recursive", names: bool = False
    ) -> Union[List[str], None]:
        """
        Fetch pinned CIDs from local node.

        Args:
            pin_type (str): The type of pinned keys to list. Can be "direct", "indirect", "recursive", or "all". Defaults to "recursive".
            names (bool): Include pin names in the output. Defaults to False.

        Returns:
            Union[List[str], None]: List of pinned CIDs. If `names` is True, returns list of json objects.
        """
        # Setting param options
        param_options = f"type={pin_type}&names={names}"
        response = requests.post(
            f"http://{self.local_gateway}:{self.api_port}/api/v0/pin/ls?{param_options}",
            timeout=10,
        )

        if response.status_code == 200:
            if response.json() != {}:
                if names:
                    return list(response.json())
                else:
                    return list(response.json()["Keys"].keys())
        else:
            print("Error fetching pinned CIDs")
            return [""]

    def getCSVDataframeFromCID(self, cid: str) -> pd.DataFrame:
        """
        Parse CSV CID to pandas dataframe.

        Args:
            cid (str): CID to retrieve.

        Returns:
            pd.DataFrame: Parsed DataFrame.
        """
        try:
            data = self.getFromCID(cid)

            # Parse for contents endpoint
            soup = BeautifulSoup(data, "html.parser")
            endpoint = f"{soup.find_all('a')[0].get('href').replace('.tech', '.io')}{soup.find_all('a')[-1].get('href')}"

            response = requests.get(endpoint, timeout=10)
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data)

            return df
        except Exception as e:
            print(f"Error with dataframe retrieval: {e}")

        # Return an empty DataFrame
        return pd.DataFrame()


class Asset:
    def __init__(
        self,
        cid: str,
        local_gateway: str,
        api_port: int,
        fetch_data: bool = False,
        name: Optional[str] = None,
    ) -> None:
        """
        Constructor for asset object.

        Args:
            cid (str): The CID associated with the object.
            local_gateway (str): Local gateway endpoint.
            api_port (int): API port.
            fetch_data (bool): Fetch data from CID. Defaults to False.
            name (Optional[str]): Name of the asset. Defaults to None.
        """
        self.cid: str = cid
        self.local_gateway = local_gateway
        self.api_port = api_port
        self.data: Optional[bytes] = None
        self.is_pinned = False

        if name:
            self.name = name
        else:
            self.name = cid

        if fetch_data:
            self.fetch()

    def __str__(self) -> str:
        return self.cid

    def _is_pinned_to_local_node(self) -> bool:
        """
        Check if CID is pinned to local node.

        Returns:
            bool: True if pinned, False otherwise.
        """
        resp = requests.post(
            f"http://{self.local_gateway}:{self.api_port}/api/v0/pin/ls?arg=/ipfs/{self.cid}",
            timeout=10,
        )
        if (resp.json().get("Keys")) and self.cid in resp.json()["Keys"]:
            self.is_pinned = True
            return True
        elif resp.json()["Type"] == "error":
            return False
        else:
            print("Error checking if CID is pinned")
            print(resp.json())
            return False

    def fetch(self) -> None:
        """
        Fetch data for the asset.
        """
        try:
            self.data = fetchCID(self.cid)
        except Exception as e:
            print(f"Error with CID fetch: {e}")

    # Pin to local kubo node
    # @ensure_data_fetched
    def pin(self) -> None:
        """
        Pin the asset to the local node.
        """
        self._is_pinned_to_local_node()
        if self.is_pinned:
            print("Content is already pinned")
        else:
            response = requests.post(
                f"http://{self.local_gateway}:{self.api_port}/api/v0/pin/add?arg={self.cid}",
                timeout=10,
            )

            if response.status_code == 200:
                print("Data pinned successfully")
                self.is_pinned = True

            else:
                print("Error pinning data")

    def addToMFS(self, filename: str, mfs_path: str) -> None:
        """
        Add CID to MFS.

        Args:
            filename (str): Name of file.
            mfs_path (str): Path in MFS.
        """
        if filename is None or filename == "":
            filename = self.name

        response = requests.post(
            f"http://{self.local_gateway}:{self.api_port}/api/v0/files/cp?arg=/ipfs/{self.cid}&arg={mfs_path}/{filename}",
            timeout=10,
        )

        if response.status_code == 200:
            print("Data added to MFS successfully")
        else:
            print("Error adding data to MFS")

    # Returns asset as np array if image
    @ensure_data_fetched
    def to_np_ndarray(self, dtype: Union[np.dtype, type] = np.float32) -> np.ndarray:
        """
        Convert asset data to numpy ndarray.

        Args:
            dtype (Union[np.dtype, type]): Data type for the ndarray. Defaults to np.float32.

        Returns:
            np.ndarray: Numpy array of the asset data.
        """
        if self.data is None:
            raise ValueError("Data for asset has not been fetched yet")
        with rasterio.open(BytesIO(self.data)) as dataset:
            return dataset.read(1).astype(dtype)
