"""
PyTest unit tests for small utility functions in the package. Tests use
lazy imports and monkeypatching for external dependencies (arcpy/boto3)
so they can run in a CI environment without those heavy packages.
"""

from pathlib import Path
import sys
import types
import importlib

import pandas as pd
import pytest

# get paths to useful resources - notably where the src directory is
self_pth = Path(__file__)
dir_test = self_pth.parent
dir_prj = dir_test.parent
dir_src = dir_prj / "src"

# insert the src directory into the path; modules will be imported inside tests
sys.path.insert(0, str(dir_src))


def test_slugify_basic():
    data = importlib.import_module("arcgis_oriented_imagery.data")
    assert data._slugify("Hello World!") == "hello-world"
    assert data._slugify("A__B") == "a-b"
    assert data._slugify("  Trim  ") == "trim"


def test_rename_dataframe_columns_basic():
    schema = importlib.import_module("arcgis_oriented_imagery.schema")
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    mapping = {"a": "alpha", "c": "gamma"}
    renamed = schema.rename_dataframe_columns(df, mapping, warn_if_extra=True)
    assert "alpha" in renamed.columns
    assert "gamma" in renamed.columns
    assert "b" in renamed.columns


def test_rename_dataframe_columns_no_matches(caplog):
    schema = importlib.import_module("arcgis_oriented_imagery.schema")
    df = pd.DataFrame({"a": [1]})
    mapping = {"x": "y"}
    renamed = schema.rename_dataframe_columns(df, mapping)
    # no rename should occur
    assert list(renamed.columns) == ["a"]


def test_rename_csv_columns(tmp_path):
    schema = importlib.import_module("arcgis_oriented_imagery.schema")
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"

    df = pd.DataFrame({"col1": [1, 2], "col2": ["x", "y"]})
    df.to_csv(input_csv, index=False)

    mapping = {"col1": "first"}
    out_path = schema.rename_csv_columns(input_csv, output_csv, mapping)
    assert out_path == output_csv
    # read back and check header
    out_df = pd.read_csv(output_csv)
    assert "first" in out_df.columns
    assert "col2" in out_df.columns


def test_rename_csv_columns_missing_input(tmp_path):
    schema = importlib.import_module("arcgis_oriented_imagery.schema")
    missing = tmp_path / "nope.csv"
    with pytest.raises(FileNotFoundError):
        schema.rename_csv_columns(missing, tmp_path / "out.csv", {"a": "b"})


def test_create_file_geodatabase_calls_arcpy(tmp_path, monkeypatch):
    called = {}

    # create a fake arcpy.management.CreateFileGDB
    def fake_create_file_gdb(parent, name):
        called['args'] = (parent, name)

    fake_arcpy_management = types.SimpleNamespace(CreateFileGDB=fake_create_file_gdb)

    # ensure any import of arcpy inside the module sees our fake
    fake_arcpy_module = types.ModuleType("arcpy")
    fake_arcpy_module.management = fake_arcpy_management
    # provide a minimal SpatialReference type so annotations in the data module
    # that reference arcpy.SpatialReference can be evaluated during import
    class _DummySpatialRef:
        def __init__(self, val=None):
            self.val = val

    fake_arcpy_module.SpatialReference = _DummySpatialRef
    monkeypatch.setitem(sys.modules, "arcpy", fake_arcpy_module)

    # import the data module now that arcpy is mocked
    # ensure we re-import the data module so it picks up the mocked arcpy
    if "arcgis_oriented_imagery.data" in sys.modules:
        del sys.modules["arcgis_oriented_imagery.data"]
    data = importlib.import_module("arcgis_oriented_imagery.data")

    # choose a non-existent gdb path
    gdb_path = tmp_path / "nested" / "my.gdb"
    # call the function
    ret = data.create_file_geodatabase(gdb_path)
    assert ret == gdb_path
    # ensure parent directory was created
    assert gdb_path.parent.exists()
    # ensure our fake CreateFileGDB was called with name
    assert called['args'][1] == "my.gdb"


def test_create_oriented_imagery_dataset_type_error(monkeypatch, tmp_path):
    # mock arcpy module so import succeeds
    class DummySR:
        def __init__(self, val=None):
            self.val = val

    fake_arcpy_module = types.ModuleType("arcpy")
    fake_arcpy_module.SpatialReference = DummySR
    monkeypatch.setitem(sys.modules, "arcpy", fake_arcpy_module)
    # ensure the data module is re-imported to pick up the fake arcpy
    if "arcgis_oriented_imagery.data" in sys.modules:
        del sys.modules["arcgis_oriented_imagery.data"]
    data = importlib.import_module("arcgis_oriented_imagery.data")

    # ensure create_file_geodatabase does not do anything
    monkeypatch.setattr(data, "create_file_geodatabase", lambda file_geodatabase_path: file_geodatabase_path)

    ds_path = tmp_path / "test.gdb" / "dataset"
    # passing a wrong type for spatial_reference should raise TypeError
    with pytest.raises(TypeError):
        data.create_oriented_imagery_dataset(ds_path, spatial_reference="not-an-int")


def test_create_oriented_imagery_dataset_calls_arcpy(monkeypatch, tmp_path):
    called = {}

    class FakeSpatialRef:
        def __init__(self, val):
            self.val = val

    def fake_create_oriented(out_dataset_path, out_dataset_name, spatial_reference, has_z=True):
        called['args'] = (out_dataset_path, out_dataset_name, spatial_reference, has_z)

    fake_arcpy_module = types.ModuleType("arcpy")
    fake_arcpy_module.SpatialReference = FakeSpatialRef
    fake_arcpy_module.management = types.SimpleNamespace(CreateOrientedImageryDataset=fake_create_oriented)
    # ensure our fake arcpy is used during import
    monkeypatch.setitem(sys.modules, "arcpy", fake_arcpy_module)

    # ensure re-import so the module binds to the mocked arcpy
    if "arcgis_oriented_imagery.data" in sys.modules:
        del sys.modules["arcgis_oriented_imagery.data"]
    data = importlib.import_module("arcgis_oriented_imagery.data")
    # also prevent create_file_geodatabase from touching disk
    monkeypatch.setattr(data, "create_file_geodatabase", lambda file_geodatabase_path: file_geodatabase_path)

    ds_path = tmp_path / "out.gdb" / "my_oim"
    ret = data.create_oriented_imagery_dataset(ds_path, spatial_reference=3857, has_z=False)
    assert ret == ds_path
    assert 'args' in called
    out_gdb, name, spatial_ref, hasz = called['args']
    assert str(out_gdb).endswith("out.gdb")
    assert name == "my_oim"
    assert isinstance(spatial_ref, FakeSpatialRef)
    assert hasz is False


def test_get_new_camera_info_tables_downloads_and_updates_manifest(monkeypatch, tmp_path):
    # Arrange: create fake boto3 client with list_objects_v2 and download_file
    calls = {"downloaded": []}

    class FakeS3Client:
        def __init__(self):
            pass

        def list_objects_v2(self, Bucket, Prefix):
            # return two objects, one CSV one other
            return {
                "Contents": [
                    {"Key": f"{Prefix}/table1.csv", "LastModified": __import__("datetime").datetime(2025,1,1)},
                    {"Key": f"{Prefix}/notes.txt", "LastModified": __import__("datetime").datetime(2025,1,1)},
                ]
            }

        def download_file(self, Bucket, Key, Filename):
            calls["downloaded"].append((Bucket, Key, Filename))
            # create a dummy file
            Path(Filename).write_text("a,b\n1,2\n")

    fake_s3 = FakeS3Client()

    def fake_boto3_client(name):
        assert name == "s3"
        return fake_s3

    monkeypatch.setattr("boto3.client", fake_boto3_client)

    # Act: call get_new_camera_info_tables
    data = importlib.import_module("arcgis_oriented_imagery.data")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    s3_path = "s3://my-bucket/prefix"
    manifest_file = out_dir / "manifest.json"

    result = data.get_new_camera_info_tables(s3_bucket_path=s3_path, local_working_directory=out_dir, manifest_file=manifest_file)

    # Assert: returned list contains the csv we created, manifest file updated, and download was called
    assert any(str(p).endswith("table1.csv") for p in result)
    assert len(calls["downloaded"]) == 1
    assert manifest_file.exists()


def test_get_new_camera_info_tables_no_contents_key(monkeypatch, tmp_path, capsys):
    # Arrange: fake boto3 client returning no 'Contents' key
    class FakeS3ClientNoContents:
        def list_objects_v2(self, Bucket, Prefix):
            return {}

        def download_file(self, Bucket, Key, Filename):
            raise RuntimeError("should not be called")

    def fake_boto3_client(name):
        assert name == "s3"
        return FakeS3ClientNoContents()

    monkeypatch.setattr("boto3.client", fake_boto3_client)

    data = importlib.import_module("arcgis_oriented_imagery.data")
    out_dir = tmp_path / "out2"
    out_dir.mkdir()
    manifest = out_dir / "manifest.json"

    # Attach a temporary stream handler to capture logger output
    import io, logging
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setLevel(logging.INFO)
    data.logger.addHandler(h)

    # Act
    result = data.get_new_camera_info_tables(s3_bucket_path="s3://bucket/prefix", local_working_directory=out_dir, manifest_file=manifest)

    # cleanup handler and read buffer
    data.logger.removeHandler(h)
    log_text = buf.getvalue()

    # Assert: no downloads, empty result, manifest should not be created
    assert result == []
    assert not manifest.exists()
    # assert the module logged the expected info message
    assert "No objects found in S3 bucket" in log_text


def test_get_new_camera_info_tables_credentials_error(monkeypatch, tmp_path, capsys):
    # Arrange: fake boto3 client that raises NoCredentialsError on list
    from botocore.exceptions import NoCredentialsError

    class FakeS3ClientCredErr:
        def list_objects_v2(self, Bucket, Prefix):
            raise NoCredentialsError()

        def download_file(self, Bucket, Key, Filename):
            raise RuntimeError("should not be called")

    def fake_boto3_client(name):
        assert name == "s3"
        return FakeS3ClientCredErr()

    monkeypatch.setattr("boto3.client", fake_boto3_client)

    data = importlib.import_module("arcgis_oriented_imagery.data")
    out_dir = tmp_path / "out3"
    out_dir.mkdir()
    manifest = out_dir / "manifest.json"

    # Attach temporary handler to capture error logs
    import io, logging
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setLevel(logging.ERROR)
    data.logger.addHandler(h)

    # Act
    result = data.get_new_camera_info_tables(s3_bucket_path="s3://bucket/prefix", local_working_directory=out_dir, manifest_file=manifest)

    data.logger.removeHandler(h)
    log_text = buf.getvalue()

    # Assert: empty result and manifest not created
    assert result == []
    assert not manifest.exists()
    # assert the module logged an error about missing credentials
    assert "AWS credentials not found" in log_text


def test_get_new_camera_info_tables_partial_manifest(monkeypatch, tmp_path):
    # Arrange: fake boto3 client with two CSVs; existing manifest has table1.csv with older timestamp
    calls = {"downloaded": []}

    class FakeS3ClientPartial:
        def list_objects_v2(self, Bucket, Prefix):
            return {
                "Contents": [
                    {"Key": f"{Prefix}/table1.csv", "LastModified": __import__("datetime").datetime(2025, 1, 2)},
                    {"Key": f"{Prefix}/table2.csv", "LastModified": __import__("datetime").datetime(2025, 1, 1)},
                ]
            }

        def download_file(self, Bucket, Key, Filename):
            calls["downloaded"].append((Bucket, Key, Filename))
            Path(Filename).write_text("a,b\n1,2\n")

    monkeypatch.setattr("boto3.client", lambda name: FakeS3ClientPartial())

    data = importlib.import_module("arcgis_oriented_imagery.data")
    out_dir = tmp_path / "out_partial"
    out_dir.mkdir()
    manifest_file = out_dir / "manifest.json"

    # create an existing manifest where table1.csv is older than S3 and table2.csv is up-to-date
    existing_manifest = {
        "table1.csv": __import__("datetime").datetime(2024, 1, 1).replace(tzinfo=__import__("datetime").timezone.utc).isoformat(),
        "table2.csv": __import__("datetime").datetime(2025, 1, 1).replace(tzinfo=__import__("datetime").timezone.utc).isoformat(),
    }
    import json

    with open(manifest_file, "w") as mf:
        json.dump(existing_manifest, mf)

    # Act
    result = data.get_new_camera_info_tables(s3_bucket_path="s3://bucket/prefix", local_working_directory=out_dir, manifest_file=manifest_file)

    # Assert: table1.csv should have been downloaded (newer), table2.csv skipped
    assert any(str(p).endswith("table1.csv") for p in result)
    assert not any(str(p).endswith("table2.csv") for p in result)
    # manifest updated: both keys should be present and table1 updated to 2025-01-02
    with open(manifest_file, "r") as mf:
        updated = json.load(mf)
    assert "table1.csv" in updated and "table2.csv" in updated
    assert updated["table1.csv"].startswith("2025-01-02")


def test_add_images_to_oriented_imagery_dataset_calls_arcpy(monkeypatch, tmp_path):
    called = {}

    def fake_add_images(in_oriented_imagery_dataset, imagery_category, input_data, include_all_fields):
        called['args'] = (in_oriented_imagery_dataset, imagery_category, input_data, include_all_fields)

    fake_arcpy_module = types.ModuleType("arcpy")
    fake_arcpy_module.management = types.SimpleNamespace(AddImagesToOrientedImageryDataset=fake_add_images)
    # SpatialReference used elsewhere - provide minimal class
    class FakeSR:
        def __init__(self, v=None):
            self.v = v

    fake_arcpy_module.SpatialReference = FakeSR
    monkeypatch.setitem(sys.modules, "arcpy", fake_arcpy_module)

    # re-import data module to bind to fake arcpy
    if "arcgis_oriented_imagery.data" in sys.modules:
        del sys.modules["arcgis_oriented_imagery.data"]
    data = importlib.import_module("arcgis_oriented_imagery.data")

    # create a fake oriented imagery dataset path
    ds_path = tmp_path / "my.gdb" / "dataset"
    ds_parent = ds_path.parent
    ds_parent.mkdir(parents=True)
    # create the dataset file to satisfy existence checks
    ds_path.write_text("")

    # create a minimal camera info csv
    cam_csv = tmp_path / "cam.csv"
    cam_csv.write_text("id,filename\n1,img1.jpg\n")

    # Prevent file-geodatabase creation from doing anything
    monkeypatch.setattr(data, "create_file_geodatabase", lambda p: p.parent)

    # Act
    ret = data.add_images_to_oriented_imagery_dataset(dataset_path=ds_path, camera_info_table=cam_csv, imagery_category="360", include_all_fields=False)

    # Assert
    assert ret == ds_path
    assert 'args' in called
    in_ds, cat, input_data, include_all = called['args']
    assert str(in_ds) == str(ds_path)
    assert cat == "360"
    assert str(input_data).endswith("cam.csv")
    assert include_all is False


def test_get_new_camera_info_tables_large_listing(monkeypatch, tmp_path):
    # Arrange: fake boto3 client returning a large listing of CSVs
    calls = {"downloaded": []}

    class FakeS3ClientLarge:
        def list_objects_v2(self, Bucket, Prefix):
            # simulate 200 csv files and a few non-csv
            contents = []
            for i in range(1, 201):
                contents.append({"Key": f"{Prefix}/table{i}.csv", "LastModified": __import__("datetime").datetime(2025, 1, 1)})
            contents.append({"Key": f"{Prefix}/notes.txt", "LastModified": __import__("datetime").datetime(2025, 1, 1)})
            return {"Contents": contents}

        def download_file(self, Bucket, Key, Filename):
            calls["downloaded"].append((Bucket, Key, Filename))
            Path(Filename).write_text("a,b\n1,2\n")

    monkeypatch.setattr("boto3.client", lambda name: FakeS3ClientLarge())

    data = importlib.import_module("arcgis_oriented_imagery.data")
    out_dir = tmp_path / "out_large"
    out_dir.mkdir()
    manifest_file = out_dir / "manifest_large.json"

    # Act
    result = data.get_new_camera_info_tables(s3_bucket_path="s3://bucket/prefix", local_working_directory=out_dir, manifest_file=manifest_file)

    # Assert: all CSVs downloaded
    assert len(calls["downloaded"]) == 200
    assert len(result) == 200
    assert manifest_file.exists()


def test_get_new_camera_info_tables_pagination(monkeypatch, tmp_path):
    # Arrange: fake boto3 client that returns IsTruncated=True (but code does not paginate)
    calls = {"list_calls": 0, "downloaded": []}

    class FakeS3ClientPagedMulti:
        def __init__(self):
            self.page = 0

        def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
            calls["list_calls"] += 1
            # first page
            if self.page == 0:
                self.page += 1
                return {
                    "Contents": [
                        {"Key": f"{Prefix}/a.csv", "LastModified": __import__("datetime").datetime(2025, 1, 1)},
                        {"Key": f"{Prefix}/b.csv", "LastModified": __import__("datetime").datetime(2025, 1, 1)},
                    ],
                    "IsTruncated": True,
                    "NextContinuationToken": "token-1",
                }
            # second page
            else:
                return {
                    "Contents": [
                        {"Key": f"{Prefix}/c.csv", "LastModified": __import__("datetime").datetime(2025, 1, 2)},
                    ],
                    "IsTruncated": False,
                }

        def download_file(self, Bucket, Key, Filename):
            calls["downloaded"].append((Bucket, Key, Filename))
            Path(Filename).write_text("x,y\n1,2\n")

    monkeypatch.setattr("boto3.client", lambda name: FakeS3ClientPagedMulti())

    data = importlib.import_module("arcgis_oriented_imagery.data")
    out_dir = tmp_path / "out_page"
    out_dir.mkdir()
    manifest_file = out_dir / "manifest_page.json"

    # Act
    result = data.get_new_camera_info_tables(s3_bucket_path="s3://bucket/prefix", local_working_directory=out_dir, manifest_file=manifest_file)

    # Assert: all pages were processed and all 3 files downloaded
    assert calls["list_calls"] == 2
    assert len(calls["downloaded"]) == 3
    assert len(result) == 3


def test_get_new_camera_info_tables_missing_token_recovers_on_retry(monkeypatch, tmp_path):
    # Simulate first response with IsTruncated=True but no NextContinuationToken,
    # and a subsequent retry returns the token and second page.
    calls = {"list_calls": 0, "downloaded": []}

    class FakeS3ClientTokenAppears:
        def __init__(self):
            self.attempts = 0

        def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
            self.attempts += 1
            calls["list_calls"] += 1
            if self.attempts == 1:
                return {
                    "Contents": [
                        {"Key": f"{Prefix}/a.csv", "LastModified": __import__("datetime").datetime(2025, 1, 1)},
                    ],
                    "IsTruncated": True,
                    # intentionally omit NextContinuationToken initially
                }
            elif self.attempts == 2:
                # retry shows token
                return {
                    "Contents": [],
                    "IsTruncated": True,
                    "NextContinuationToken": "tok-1",
                }
            else:
                # final page
                return {"Contents": [{"Key": f"{Prefix}/b.csv", "LastModified": __import__("datetime").datetime(2025, 1, 2)}], "IsTruncated": False}

        def download_file(self, Bucket, Key, Filename):
            calls["downloaded"].append((Bucket, Key, Filename))
            Path(Filename).write_text("x,y\n1,2\n")

    monkeypatch.setattr("boto3.client", lambda name: FakeS3ClientTokenAppears())

    data = importlib.import_module("arcgis_oriented_imagery.data")
    out_dir = tmp_path / "out_token"
    out_dir.mkdir()
    manifest_file = out_dir / "manifest_token.json"

    result = data.get_new_camera_info_tables(s3_bucket_path="s3://bucket/prefix", local_working_directory=out_dir, manifest_file=manifest_file)

    # should have processed both pages (downloaded a.csv and b.csv)
    assert len(calls["downloaded"]) == 2
    assert len(result) == 2


def test_get_new_camera_info_tables_missing_token_stops(monkeypatch, tmp_path):
    # Simulate IsTruncated=True with no token and retries do not produce a token
    class FakeS3ClientNoToken:
        def __init__(self):
            self.calls = 0

        def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
            self.calls += 1
            return {"Contents": [{"Key": f"{Prefix}/x.csv", "LastModified": __import__("datetime").datetime(2025, 1, 1)}], "IsTruncated": True}

        def download_file(self, Bucket, Key, Filename):
            Path(Filename).write_text("x,y\n1,2\n")

    monkeypatch.setattr("boto3.client", lambda name: FakeS3ClientNoToken())

    data = importlib.import_module("arcgis_oriented_imagery.data")
    out_dir = tmp_path / "out_notok"
    out_dir.mkdir()
    manifest_file = out_dir / "manifest_notok.json"

    result = data.get_new_camera_info_tables(s3_bucket_path="s3://bucket/prefix", local_working_directory=out_dir, manifest_file=manifest_file)

    # function should stop after retries and download only the first page content
    assert len(result) == 1
