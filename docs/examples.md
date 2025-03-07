# Using the `ipfs-stac` library

This pages provides some examples on how to use the `ipfs-stac` library.

## Usage

### Create a client object

Import the client module and create a new client object. The client object can be used to interact with the STAC API and IPFS.

``` python
from ipfs_stac import client
easier = client.Web3()
```

You can also specify a specific STAC API endpoint.

``` python
easier = client.Web3(stac_endpoint="https://stac.easierdata.info")
```

If you want to retrieve data from your local IPFS node or a known IPFS HTTP gateway, you can specify the endpoint in the `local_gateway` argument.

``` python
easier = client.Web3(local_gateway="127.0.0.1")
```

If your local IPFS gateway has been configured beyond the defaults, you can override the default gateway port and [KUBO RPC API](https://docs.ipfs.tech/reference/kubo/rpc/) port.

``` python
easier = client.Web3(local_gateway="127.0.0.1", gateway_port=8081, api_port=5050)
```

### Fetch a CID from IPFS

Retrieval of content from IPFS is done by providing the CID of the content. The `getFromCID` method can be used to retrieve the content from IPFS. The example below retrieves the content from the CID `QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx` and prints it.

``` python
# Simple hello world example
data = easier.getFromCID("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
print(data)

"""
hello worlds
"""
```

### Query Content from STAC

The `searchSTAC` method can be used to query a STAC catalog. For a list of query parameters, refer to this [table](https://github.com/radiantearth/stac-api-spec/tree/release/v1.0.0/item-search#query-parameter-table).

The example below retrieves all items from the `landsat-c2l1` collection that are within a bounding box.

```python

bounding_box = [-76.964657, 38.978967, -76.928008, 39.002783]
landsat_items = easier.searchSTAC(bbox=bounding_box, collections=["landsat-c2l1"]) 
len(landsat_items) # 2
landsat_items
[<Item id=LC09_L1TP_015033_20221015_20221015_02_T1>, <Item id=LC09_L1GT_015033_20211231_20220122_02_T2>]
```

If we wanted to understand the assets our items contain, we can use the `getAssetNames` method to get a list of assets available in `landsat_items` object.

```python
easier.getAssetNames(landsat_items)
['ANG.txt', 'MTL.json', 'MTL.txt', 'MTL.xml', 'SAA', 'SZA', 'VAA', 'VZA', 'blue', 'cirrus', 'coastal', 'green', 'index', 'lwir11', 'lwir12', 'nir08', 'pan', 'qa_pixel', 'qa_radsat', 'red', 'reduced_resolution_browse', 'swir16', 'swir22', 'thumbnail']
```

Let's retrieve the content of the `nir08` asset from the first item in the `landsat_items` object.

```python
band = easier.getAssetFromItem(landsat_items[0], 'nir08')
```

or even retrieve multiple assets from the item.

```python
bands = easier.getAssetsFromItem(item, ["blue", "red"]) # Returns array of assets
```

### The Asset Object

Up to this point, we've used STAC to identify what collections are available, queried items from a collection and specified which assets we want to retrieve. Next, we'll retrieve the content from IPFS for the assets we've selected.

In order to retrieve content from IPFS, we'll need to specify a CID.  Let's get the CID for single band we retrieved earlier.

```python
band.cid
'QmZkWaKSuVhFKtAwNbxSogcT6hXHMksXjhgqLu6AXHSUKq'
```

and then fetch the content from IPFS.

```python
band.fetch()
print(band.data) # b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x...

# Alternatively, you can also transform the asset data in different formats such as a numpy array
band_np = band.to_np_ndarray()
print(band_np) # [[0. 0. 0. ... 0. 0. 0.]
               #  [0. 0. 0. ... 0. 0. 0.]
               #  [0. 0. 0. ... 0. 0. 0.]
               #  ...
               #  [0. 0. 0. ... 0. 0. 0.]
               #  [0. 0. 0. ... 0. 0. 0.]
               #  [0. 0. 0. ... 0. 0. 0.]]
```
