== About ==

ArchiveFS is a FUSE file system used for archiving and backup.  Its primary function is to ensure that multiple copies of a file are only represented as a single file.  The representation of the file system is intentionally kept simple and consists just of a single SQLite3 database file and table (which can be dumped into a text file), together with a directory full of files. 

The file system is not intended for general purpose computing, but mostly for copying data in and out.  It seems to be working reasonably well for backup, and even file system intensive operations like software builds seem to complete OK.  Please give it a good try and workout, but don't blame me if you lose any data.  

== Usage ==

Just check out the source code.  You do need the python-fuse and python-sqlite3 packages (Ubuntu) or their equivalents.

To start it up, use a command like:

{{{
$ python archivefs.py -o root=/somewhere/FSDATA /my/mountpoint
$ echo hello world > /my/mountpoint/new-file
$ cat /my/mountpoint/new-file
}}}

The `root` directory must exist and be writable by you.  The `root` directory contains the database file (`DB`), a working directory for temporary files (`WORKING`), and an archival directory containing the actual, permanent files (`ARCHIVE`).  The file system will create those if they don't already exist.

When you're done, you should unmount the directory as usual:

{{{
$ fusermount -u /my/mountpoint
}}}

It's intended to be used with something like:

{{{
cp -av /home/tmb /backup/tmb-$(date)
}}}

You can get some file metadata via getfattr and attr:

  * `attr -g _id` _file_ -- the unique file id
  * `attr -g _storage` _file_ -- the path to the actual file
  * `attr -g _instances` _file_ -- a list of all paths referring to this content

Note the following points:

  * file permissions aren't enforced (but are recorded)
  * link counts are not preserved
  * deleting a file only deletes its entry, it doesn't recover the space automatically

There are a number of things I can't find good documentation and that I therefore don't quite understand in fuse-python:

  * hardlinks and concurrent updates through different paths
  * the degree of threading (apparently, not much, but enough to cause occasional problems)
  * how mmap is handled

You can reconstruct a directory tree easily from an md5sum dump and the contents of the archive disk; you don't need FUSE.  To create such a dump manually, just write:

{{{
$ find . -type f -print0 | xargs -0 md5sum > my.md5sums
}}}

(I'll upload some scripts for this at some point.)

== History ==

This code replaces (and is based on) a bunch of shell scripts I've been using for backup for a couple of decades that also used checksums for storage but stored the mapping in a plain text file.

The reason why a file system is nicer than the scripts is because it's possible not only to copy into the archival tree, but also untar tar files in it directly, copy data in remotely, etc.  With FUSE, it's finally easy and portable enough to do this (last time I looked into doing this, this still required a lot of painful kernel-level C programming.) 

== Internals ==

It's written in Python using the python-fuse package.

The representation of the file system is pretty simple:

  * root/DB -- sqlite3 database file containing metadata and ids
  * root/ARCHIVE/xx/yy/xxyyzzzzz... -- the actual content, stored by id
    * to keep directory size down, this has two levels of directories
  * root/WORKING/zzzzzzzz... -- temporary working files

== TODO ==

There are a bunch of things to be done:

  * important
    * clean up the code
    * write a text file dumper for the database
    * smart command line tools for local and remote copies/sync
    * garbage collecting defunct working files on startup
    * garbage collecting defunct archival files on demand (after a big removal)
    * automatic garbage collection of defunct archival files upon deletion
    * add metadata handling and searchrecord checksum and discard)
    * well-known checksums (just
    * transparent gzip compression/decompression of chunks
  * would be nice
    * record-and-discard
      * well-known checksum (can retrieve from the web, maybe store URL)
      * by file name
      * by mime type
    * separate directory and file name columns to make dir listings faster
    * tokenize directory names to save space
    * id available via extended attribute
    * speed it up by caching and other tricks
    * better multithreading (maybe port to IronPython)
    * record user ids in text form and resolve at runtime
    * fix global scope for fs variable
    * transparently handle files inside archives
    * write a test suite and perform more extensive testing
    * perform explicit in-memory buffering for checksumming and copying
    * use a larger checksum to make collisions less likely
    * add non-FUSE command line tools for storing and accessing the data
    * handle extended attributes
    * tools for reporting logical vs physical usage
    * move small file operations in memory
    * transparent mounting of the underlying file system
  * long term ideas (maybe a different project)
    * handle file parts by partitioning files at type-dependent boundaries 
      * e.g., paragraph boundaries, MP3 chunks, mbox message boundaries, etc.
      * transparently disassemble and assemble archive formats
    * S3 backend
    * stick very small files into the database
    * distributed storage across disks
    * distributed storage across the network
    * change tracking
    * time-machine like functionality
      * i.e. represent trees at different points in time explicitly
      * also saves database space for frequent backups
      * this needs to have a notion of a completed checkpoint, so...
        * archivefs-open-replica old-tree new-tree
        * rsync ... source new-tree
        * archivefs-close-replica new-tree old-tree
