import h5py
import numpy
import numpy.testing
import pytest

from .common import ut, TestCase


@ut.skipUnless(h5py.version.hdf5_version_tuple >= (1, 8, 11), 'Direct Chunk Writing requires HDF5 >= 1.8.11')
class TestWriteDirectChunk(TestCase):
    def test_write_direct_chunk(self):

        filename = self.mktemp().encode()
        with h5py.File(filename, "w") as filehandle:

            dataset = filehandle.create_dataset("data", (100, 100, 100),
                                                maxshape=(None, 100, 100),
                                                chunks=(1, 100, 100),
                                                dtype='float32')

            # writing
            array = numpy.zeros((10, 100, 100))
            for index in range(10):
                a = numpy.random.rand(100, 100).astype('float32')
                dataset.id.write_direct_chunk((index, 0, 0), a.tobytes(), filter_mask=1)
                array[index] = a


        # checking
        with h5py.File(filename, "r") as filehandle:
            for i in range(10):
                read_data = filehandle["data"][i]
                numpy.testing.assert_array_equal(array[i], read_data)


@ut.skipUnless(h5py.version.hdf5_version_tuple >= (1, 10, 2), 'Direct Chunk Reading requires HDF5 >= 1.10.2')
@ut.skipIf('gzip' not in h5py.filters.encode, "DEFLATE is not installed")
class TestReadDirectChunk(TestCase):
    def test_read_compressed_offsets(self):

        filename = self.mktemp().encode()
        with h5py.File(filename, "w") as filehandle:

            frame = numpy.arange(16).reshape(4, 4)
            frame_dataset = filehandle.create_dataset("frame",
                                                      data=frame,
                                                      compression="gzip",
                                                      compression_opts=9)
            dataset = filehandle.create_dataset("compressed_chunked",
                                                data=[frame, frame, frame],
                                                compression="gzip",
                                                compression_opts=9,
                                                chunks=(1, ) + frame.shape)
            filter_mask, compressed_frame = frame_dataset.id.read_direct_chunk((0, 0))
            # No filter must be disabled
            self.assertEqual(filter_mask, 0)

            for i in range(dataset.shape[0]):
                filter_mask, data = dataset.id.read_direct_chunk((i, 0, 0))
                self.assertEqual(compressed_frame, data)
                # No filter must be disabled
                self.assertEqual(filter_mask, 0)

    def test_read_uncompressed_offsets(self):

        filename = self.mktemp().encode()
        frame = numpy.arange(16).reshape(4, 4)
        with h5py.File(filename, "w") as filehandle:
            dataset = filehandle.create_dataset("frame",
                                                maxshape=(1,) + frame.shape,
                                                shape=(1,) + frame.shape,
                                                compression="gzip",
                                                compression_opts=9)
            # Write uncompressed data
            DISABLE_ALL_FILTERS = 0xFFFFFFFF
            dataset.id.write_direct_chunk((0, 0, 0), frame.tobytes(), filter_mask=DISABLE_ALL_FILTERS)

        # FIXME: Here we have to close the file and load it back else
        #     a runtime error occurs:
        #     RuntimeError: Can't get storage size of chunk (chunk storage is not allocated)
        with h5py.File(filename, "r") as filehandle:
            dataset = filehandle["frame"]
            filter_mask, compressed_frame = dataset.id.read_direct_chunk((0, 0, 0))

        # At least 1 filter is supposed to be disabled
        self.assertNotEqual(filter_mask, 0)
        self.assertEqual(compressed_frame, frame.tobytes())

    def test_read_write_chunk(self):

        filename = self.mktemp().encode()
        with h5py.File(filename, "w") as filehandle:

            # create a reference
            frame = numpy.arange(16).reshape(4, 4)
            frame_dataset = filehandle.create_dataset("source",
                                                      data=frame,
                                                      compression="gzip",
                                                      compression_opts=9)
            # configure an empty dataset
            filter_mask, compressed_frame = frame_dataset.id.read_direct_chunk((0, 0))
            dataset = filehandle.create_dataset("created",
                                                shape=frame_dataset.shape,
                                                maxshape=frame_dataset.shape,
                                                chunks=frame_dataset.chunks,
                                                dtype=frame_dataset.dtype,
                                                compression="gzip",
                                                compression_opts=9)

            # copy the data
            dataset.id.write_direct_chunk((0, 0), compressed_frame, filter_mask=filter_mask)

        # checking
        with h5py.File(filename, "r") as filehandle:
            dataset = filehandle["created"][...]
            numpy.testing.assert_array_equal(dataset, frame)


@pytest.mark.skipif(
    h5py.version.hdf5_version_tuple < (1, 10, 2),
    reason="Direct chunk read requires HDF5 >= 1.10.2"
)
class TestReadDirectChunkToBuffer:

    def test_uncompressed_data(self, writable_file):
        ref_data = numpy.arange(16).reshape(4, 4)
        dataset = writable_file.create_dataset(
            "uncompressed", data=ref_data, chunks=ref_data.shape)

        # Read to numpy array
        out_ndarray = numpy.zeros_like(ref_data)
        filter_mask, nbytes = dataset.id.read_direct_chunk_tobuffer((0, 0), out_ndarray)

        assert numpy.array_equal(out_ndarray, ref_data)
        assert filter_mask == 0
        assert nbytes == ref_data.nbytes

        # Read to bytearray
        out_bytearray = bytearray(ref_data.nbytes)
        filter_mask, nbytes = dataset.id.read_direct_chunk_tobuffer((0, 0), out_bytearray)

        assert numpy.array_equal(
            numpy.frombuffer(out_bytearray, dtype=ref_data.dtype).reshape(ref_data.shape),
            ref_data,
        )
        assert filter_mask == 0
        assert nbytes == ref_data.nbytes

    @pytest.mark.skipif(
        h5py.version.hdf5_version_tuple < (1, 10, 5),
        reason="chunk info requires HDF5 >= 1.10.5",
    )
    def test_compressed_data(self, writable_file):
        ref_data = numpy.arange(16).reshape(4, 4)
        dataset = writable_file.create_dataset(
            "gzip",
            data=ref_data,
            chunks=ref_data.shape,
            compression="gzip",
            compression_opts=9,
        )
        chunk_info = dataset.id.get_chunk_info(0)

        # read to bytearray
        out = bytearray(chunk_info.size)
        filter_mask, nbytes = dataset.id.read_direct_chunk_tobuffer(
            chunk_info.chunk_offset,
            out,
        )
        assert filter_mask == chunk_info.filter_mask
        assert nbytes == chunk_info.size
        assert out == dataset.id.read_direct_chunk(chunk_info.chunk_offset)[1]
