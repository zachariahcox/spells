"""
implement a set that stores data on disk
"""
import sys
import os
import shutil

class FileSystemSet():
    data_directory_name = "unique_lines"
    data_directory = data_directory_name
    max_files_per_bucket = 1
    tri_length = 0
    folder_depth = 1

    def __init__(self, directory):
        self.data_directory = directory

    def __del__(self):
        self.cleanup(self.data_directory)

    def has(self, key):
        """return True if key in dictionary"""
        file_name = self.file_hash(key)
        directory = self.file_dir(file_name, self.data_directory)
        return os.path.exists(os.path.join(directory, file_name))

    def add(self, key):
        """
        add to set
        return True if added, False if already existed
        """
        file_name = self.file_hash(line)
        directory = self.file_dir(file_name, self.data_directory)

        if not os.path.exists(os.path.join(directory, file_name)):
            # this is a new hash
            if not os.path.exists(directory):
                os.makedirs(directory)
            else:
                # how many files are in this directory?
                #   we may need to rebalance
                count = 0
                for f in os.scandir(directory):
                    if f.is_file():
                        count += 1
                if count >= self.max_files_per_bucket:
                    # rebalance and try again with the update hashing function parameters
                    self.rebalance()
                    return self.add(line)

            # write new file
            with open(os.path.join(directory, file_name), 'w') as new_file:
                new_file.write(line + "\n")

        else:
            # we have a hash collision -- this might be a dup
            line_count = 0
            with open(os.path.join(directory, file_name)) as f:
                for l in f.readlines():
                    line_count += 1
                    if line == l.rstrip():
                        # we've seen this line before
                        return False

            # deal with collision
            if line_count < self.max_files_per_bucket:
                # we're under the scan cap, so just append to the end
                with open(os.path.join(directory, file_name), 'a') as f:
                    f.write(line + "\n") # add colliding line to end?
            else:
                # we're over the scanning limit.
                # there have been too many hash collisions.
                # TODO: consider changing algorithms?
                raise Exception()

        return True

    def new_directory_name(self):
        return "_".join([
            self.data_directory_name,
            str(self.tri_length),
            str(self.folder_depth)
            ])

    def file_dir(self, file_name, root):
        sub_dirs = self.chunk(file_name, self.tri_length)[:self.folder_depth]
        directory = os.path.join(root, *sub_dirs)
        return directory

    def file_hash(self, line):
        return str(abs(hash(line)))

    def rebalance(self):
        """
        create a new storage location for the rehashed content
        """
        # change directory generation function
        self.tri_length += 1
        # folder_depth += 1

        # new root directory
        new_data_directory_name = self.new_directory_name()

        # insert data
        for root, _, files in os.walk(self.data_directory):
            for f in files:
                d = self.file_dir(f, new_data_directory_name)
                os.makedirs(d, exist_ok=True)
                shutil.move(os.path.join(root, f), os.path.join(d, f))

        # clean up old data
        self.cleanup(self.data_directory)
        self.data_directory = new_data_directory_name

    def chunk(self, array, size):
        """
        split array into subarrays of length 'size'
        """
        if size < 1:
            return []

        return [array[i:i+size] for i in range(0, len(array), size)]

    def cleanup(self, root):
        if os.path.exists(root):
            shutil.rmtree(root)

if __name__ == "__main__":

    s = FileSystemSet("uniq")

    # print line if not in set
    for line in ["a", "d", "b", "c", "d", "a", "e", "f", "g", "c"]:
        if s.add(line):
            print(line)

    # delete set
    del s