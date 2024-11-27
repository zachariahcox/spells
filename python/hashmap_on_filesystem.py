"""
implement a set that stores data on disk
"""
import os
import shutil

class FileSystemSet():
    data_directory_name = "FileSystemSetData"
    data_directory = data_directory_name
    max_files_per_directory = 1
    max_collisions_per_file = 1
    tri_length = 0 # how long should directory path components be?
    folder_depth = 1 # how many path components to use from the hash

    def __init__(self, directory):
        self.data_directory_name = directory
        self.data_directory = self.new_directory_name()

    def __del__(self):
        self.cleanup(self.data_directory)

    def has(self, key):
        """
        return True if set contains key
        """
        file_name = self.file_hash(key)
        directory = self.file_dir(file_name, self.data_directory)
        if not os.path.exists(os.path.join(directory, file_name)):
            return False

        with open(os.path.join(directory, file_name)) as f:
            for l in f.readlines():
                if key == l.rstrip():
                    # we've seen this line before
                    return False
        return True

    def add(self, key):
        """
        add key to set
        return True if set mutated, False
        """
        file_name = self.file_hash(key)
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
                if count >= self.max_files_per_directory:
                    # rebalance and try again with the update directory parameters
                    self.rebalance()
                    return self.add(key)

            # write new file
            with open(os.path.join(directory, file_name), 'w') as new_file:
                new_file.write(key + "\n")

        else:
            # we have a hash collision -- this might be a dup
            collision_count = 0
            with open(os.path.join(directory, file_name)) as f:
                for l in f.readlines():
                    collision_count += 1
                    if key == l.rstrip():
                        # we've seen this line before
                        return False

            # append if possible
            if collision_count < self.max_collisions_per_file:
                # we're under the scan cap, so just append to the end
                with open(os.path.join(directory, file_name), 'a') as f:
                    f.write(key + "\n") # add colliding line to end?
            else:
                # we're over the scanning limit. there have been too many hash collisions.
                raise Exception()

        return True

    def new_directory_name(self):
        return "_".join([
            self.data_directory_name,
            str(self.tri_length),
            str(self.folder_depth)
            ])

    def file_dir(self, file_name, root):
        """
        build a folder structure based on the file name
        """
        sub_dirs = self.chunk(file_name, self.tri_length)[:self.folder_depth]
        directory = os.path.join(root, *sub_dirs)
        return directory

    def file_hash(self, line):
        return str(abs(hash(line)))

    def rebalance(self):
        """
        ensure that no directory has more than self.max_files_per_directory files in it.
        ensure that no file has more than self.max_collisions_per_file lines in it.
        """

        # change directory generation function
        self.tri_length += 1 # reduce chance of directory collision by 1/N, where N is base of the hash space? (10 for base-10 numeric hash)
        # folder_depth += 1

        # change hash function?
        changed_hash_function = False


        # new root directory
        old_data_directory = self.data_directory
        self.data_directory = self.new_directory_name()

        # restructure data to avoid massive lists of files per directory
        for root, _, files in os.walk(old_data_directory):
            for f in files:
                if changed_hash_function:
                    # f is a file that contains all the keys that hash to its name.
                    # rehash them all with the new function
                    with open(os.path.join(root, f)) as keys:
                        for key in keys.readlines():
                            self.add(key.rstrip())
                else:
                    # just move file of collisions to the new directory
                    d = self.file_dir(f, self.data_directory)
                    os.makedirs(d, exist_ok=True)
                    shutil.move(
                        src = os.path.join(root, f),
                        dst = os.path.join(d, f)
                        )

        # remove old data
        self.cleanup(old_data_directory)

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