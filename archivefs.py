import os,sys,re,math,stat,errno,fuse,sqlite3,random,shutil
from os.path import join,normpath,dirname,basename,relpath
from os.path import split as splitpath
from time import time
from subprocess import *
import sqlite3

fuse.fuse_python_api = (0, 2)

def debug(*args):
    # print "---------"," ".join([str(s) for s in args])
    pass
def note(*args):
    # print "*********"," ".join([str(s) for s in args])
    pass
def warn(*args):
    print "*WARNING*"," ".join([str(s) for s in args])

def flag2mode(flags):
    md = {os.O_RDONLY: 'r', os.O_WRONLY: 'w', os.O_RDWR: 'w+'}
    m = md[flags & (os.O_RDONLY | os.O_WRONLY | os.O_RDWR)]
    if flags | os.O_APPEND:
        m = m.replace('w', 'a', 1)
    return m

class MyStat(fuse.Stat):
    def __init__(self,mode=None):
        if mode is None:
            self.st_mode = stat.S_IFDIR | 0755
        else:
            self.st_mode = mode
        self.st_ino = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0
        self.st_nlink = 2
        self.st_size = 4096
        self.st_uid = 0
        self.st_gid = 0
        self.st_blocks = 1
        self.st_blksize = 4096
        self.st_rdev = 0
        self.st_dev = 0

class SqlFileStore:
    """An abstraction that encapsulates the 'file system' semantics;
    methods are somewhat different from POSIX, since this actually
    implements the archive file system (combination of database and
    file system storage)."""
    def __init__(self,base):
        self.DBFILE = join(base+"/DB")
        self.ARCHIVE = join(base+"/ARCHIVE")
        self.WORKING = join(base+"/WORKING")
        self.conn = sqlite3.connect(self.DBFILE)
        self.conn.row_factory = sqlite3.Row
        try: self.make_tables()
        except: pass
        self.mkentry("/",mode=0777|stat.S_IFDIR)
        if not os.path.exists(self.ARCHIVE):
            os.mkdir(self.ARCHIVE)
        if not os.path.exists(self.WORKING):
            os.mkdir(self.WORKING)
    def archive_path(self,tag):
        assert "/" not in tag
        dir = re.sub(r'(...)(...).*','\\1/\\2',tag)
        destdir = join(self.ARCHIVE,dir)
        if not os.path.exists(destdir):
            os.makedirs(destdir)
        return join(destdir,tag)
    def make_tables(self):
        """Create the initial database tables."""
        c = self.conn.cursor()
        c.execute("""
        create table files (
        path text unique,
        mode integer,
        size integer,
        atime real,
        mtime real,
        ctime real,
        id text not null,
        symlink text
        )
        """)
        c.close()
        self.conn.commit()
    def entry(self,path):
        path = normpath(path)
        c = self.conn.cursor()
        c.execute("select * from files where path=?",(path,))
        file = c.fetchone()
        c.close()
        return file
    def id(self,path):
        """Return the current real path for the file."""
        file = self.entry(path)
        if file is None: return None
        return file["id"]
    def setId(self,path,id):
        """Update the current real path for the file."""
        c = self.conn.cursor()
        c.execute("update files set id=? where path=?",(id,path))
        self.conn.commit()
        c.close()
    def mode(self,path):
        """Return the POSIX  file mode for the given path."""
        file = self.entry(path)
        if file is None: return None
        return file["mode"]
    def exists(self,path):
        """Check whether the given path exists."""
        return self.mode(path) is not None
    def isdir(self,path):
        """Check whether the given path is a directory."""
        mode = self.mode(path)
        return mode is not None and (mode&stat.S_IFDIR)
    def checkdir(self,path):
        dir = dirname(path)
        if not self.isdir(path):
            raise IOError(errno.EINVAL,path)
    def delete(self,path):
        """Delete the given path unconditionally (no checks)."""
        debug("delete",path)
        path = normpath(path)
        c = self.conn.cursor()
        c.execute("delete from files where path=?",(path,))
        self.conn.commit()
        c.close()
    def rmdir(self,path):
        """Delete a directory, with the usual UNIX checks."""
        debug("rmdir",path)
        path = normpath(path)
        c = self.conn.cursor()
        c.execute("select * from files where path=?",(path,))
        if c.fetchone() is None: raise IOError(errno.ENOENT,path)
        c.execute("select * from files where path like ?",(path+"/%",))
        if c.fetchone() is not None: raise IOError(errno.ENOTEMPTY,path)
        c.execute("delete from files where path=?",(path,))
        self.conn.commit()
        c.close()
    def listdir(self,path):
        """Return a list of the entries in the given directory."""
        dir = normpath(path)
        if dir[-1]!="/": dir += "/"
        entries = [ '.', '..' ]
        c = self.conn.cursor()
        c.execute("select * from files where path like ?",(dir+"%",))
        prefix = len(dir)
        for file in c:
            name = file["path"][prefix:]
            if name=="": continue
            if "/" in name: continue
            entries += [name]
        for entry in entries:
            yield entry.encode("utf8")
        c.close()
    def chmod(self,path,mode):
        path = normpath(path)
        old = self.mode(path)
        mode = (old&~0777)|(mode&0777)
        c = self.conn.cursor()
        c.execute("update files set mode=? where path=?",(mode,path))
        self.conn.commit()
        c.close()
    def utime(self,path,atime,mtime):
        path = normpath(path)
        c = self.conn.cursor()
        c.execute("update files set atime=?, mtime=? where path=?",
                  (atime,mtime,path))
        self.conn.commit()
        c.close()
    def chown(self,path,user):
        return
    def mkentry(self,path,mode=0666,when=time(),id="!",symlink=None):
        """Make a new path entry for the given path and with the given mode.
        Uses the current time for all the file times."""
        debug("mkentry",path,mode,id,symlink)
        assert id!=""
        assert id!=None
        path = normpath(path)
        c = self.conn.cursor()
        c.execute("""
            insert or replace into files
            (path,mode,atime,mtime,ctime,id,symlink)
            values (?,?,?,?,?,?,?)
        """,(path,mode,when,when,when,id,symlink))
        self.conn.commit()
        c.close()
    def symlink(self,content,path):
        debug("fs symlink",content,path)
        path = normpath(path)
        self.mkentry(path,mode=stat.S_IFLNK|0777,symlink=content)
    def readlink(self,path):
        path = normpath(path)
        file = self.entry(path)
        if file is None: raise IOError(errno.ENOENT,path)
        content = file["symlink"]
        if content is None: raise IOError(errno.EINVAL,path)
        content = content.encode("utf8")
        return content
    def getattr(self,path):
        debug("getattr",path)
        path = normpath(path)
        c = self.conn.cursor()
        c.execute("select * from files where path=?",(path,))
        file = c.fetchone()
        if file is None: raise IOError(errno.ENOENT,path)
        id = file["id"]
        mode = file["mode"]
        st = MyStat()
        if id!="!":
            if os.path.exists(id):
                # use the actual files for size calculations
                base = os.lstat(id)
                st.st_size = base.st_size
                st.st_blocks = base.st_blocks
                st.st_blksize = base.st_blksize
            else:
                # if it's not a directory, it should have
                # some file corresponding to it
                if not (mode&stat.S_IFDIR):
                    debug("getattr",id,"not found for",path)
        st.st_atime = int(file["atime"])
        st.st_mtime = int(file["mtime"])
        st.st_ctime = int(file["ctime"])
        st.st_mode = file["mode"]
        c.close()
        return st

class ArchiveFile:
    def __init__(self,path,flags,mode=0666):
        """Initializes an open ArchiveFile.  This
        implements the copy-on-write semantics."""
        debug("...init",path,flags,mode)
        self.keep_cache = 0
        self.direct_io = 0
        self.path = path
        self.flags = flags
        self.mode = mode
        self.changed = 0
        self.file = None
        self.fd = None
        self.working = 0
        # fs.checkdir(path)
        if flags&os.O_CREAT:
            id = self.open_working(path,flags)
            fs.mkentry(path,mode=mode)
        else:
            self.working = 0
            file = fs.entry(path)
            if file is None:
                raise IOError(errno.ENOENT,path)
            id = file["id"]
            if id=="!": id = "/dev/null"
            self.open_(id,os.O_RDONLY)
    def open_(self,path,flags,mode=0600):
        """Opens the given path and substitutes it as the
        file to be used for I/O operations."""
        debug("...open_",path,flags,mode)
        if self.file is not None:
            self.file.close()
        stream = os.open(path,flags,mode)
        self.current = path
        self.file = os.fdopen(stream,flag2mode(flags))
        self.fd = self.file.fileno()
    def open_working(self,path,flags):
        wpath = "_"+str(random.uniform(0.0,1.0))[2:]
        id = join(fs.WORKING,wpath)
        self.open_(id,flags|os.O_CREAT)
        self.working = 1
    def switch_to_writable(self):
        if not self.working:
            self.open_working(self.path,self.flags)
            # check whether the file contains previous content;
            # if so, we copy it over before returning
            id = fs.id(self.path)
            if id!="!":
                note("copying",id)
                with open(id,"r") as stream:
                    shutil.copyfileobj(stream,self.file)
            # note that we're not updating the id in the database
            # concurrent updates happen in separate copies and the
            # last close wins
            self.working = 1

    # this goes back to the store
        
    def fgetattr(self,*args):
        return fs.getattr(self.path)

    # these methods don't care what is open

    def read(self, length, offset):
        self.file.seek(offset)
        return self.file.read(length)
    def _fflush(self):
        if 'w' in self.file.mode or 'a' in self.file.mode:
            self.file.flush()
    def fsync(self, isfsyncfile):
        self._fflush()
        if isfsyncfile and hasattr(os, 'fdatasync'):
            os.fdatasync(self.fd)
        else:
            os.fsync(self.fd)
    def flush(self):
        self._fflush()
        # cf. xmp_flush() in fusexmp_fh.c
        os.close(os.dup(self.fd))

    # these methods need to switch from a read-only file
    # to a writable file if necessary
        
    def write(self, buf, offset):
        self.switch_to_writable()
        self.file.seek(offset)
        self.file.write(buf)
        return len(buf)
    def ftruncate(self, len):
        self.switch_to_writable()
        self.file.truncate(len)

    # this needs to check
        
    def release(self, flags):
        debug("release",self.working,self.path)
        if self.working:
            tag = os.popen("md5sum %s | cut -f 1 -d ' '" % self.current).read()
            tag = tag[:-1]
            debug("tag",tag)
            dest = fs.archive_path(tag)
            debug("archive_path",dest)
            if os.path.exists(dest):
                debug("EXISTS",dest,"for",self.path)
                os.unlink(self.current)
                debug("unlinked",self.current)
            else:
                note("CREATING",dest,"for",self.path)
                os.chmod(self.current,0400)
                debug("move",self.current,dest)
                shutil.move(self.current,dest)
                debug("moved",self.current)
                assert not os.path.exists(self.current)
            debug("setid",self.path,dest)
            fs.setId(self.path,dest)
        self.file.close()

class ArchiveFS(fuse.Fuse):
    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)
        try:
            make_tables()
            self.mkdir("/",0777)
            self.mkdir("/DUMMY",0777)
        except:
            pass
    def main(self,*a,**kw):
        # This global is used by ArchiveFile
        # no clean way of doing this right in the current FUSE API
        global fs
        print "mounting on",self.root
        fs = SqlFileStore(self.root)
        self.fs = fs
        self.file_class = ArchiveFile
        return fuse.Fuse.main(self,*a,**kw)
    def getattr(self, path, *args):
        if len(args)>0:
            not("getattr",path,args)
        return self.fs.getattr(path)
    def readdir(self, path, offset):
        for entry in self.fs.listdir(path):
            yield fuse.Direntry(entry)
    def mkdir(self, path, mode):
        # self.fs.checkdir(path)
        if self.fs.exists(path):
            return -errno.EEXISTS
        self.fs.mkentry(path,mode=mode|stat.S_IFDIR)
        return 0
    def access(self,path,which):
        mode = self.fs.mode(path)
        if not mode: return -errno.ENOENT
        return 0
    def rmdir(self, path):
        self.fs.rmdir(path)
        return 0
    def mknod(self, path, mode, dev):
        return 0
    def unlink(self, path):
        self.fs.delete(path)
        return 0
    def rename(self, pathfrom, pathto):
        self.fs.rename(pathfrom,pathto)
        return 0
    def truncate(self,path,len):
        if len>0: raise IOError(errno.ENOSYS,path)
        self.fs.delete(path)
        self.fs.mkentry(path)
        return 0
    def chmod(self,path,mode):
        self.fs.chmod(path,mode)
        return 0
    def chown(self,path,*args):
        return 0
    def utime(self,path,times):
        if times == None:
            times = (time.time(), time.time())
        fs.utime(path,times[0],times[1])
    def readlink(self,path):
        content = self.fs.readlink(path)
        debug("readlink",path,"->",content)
        return content
    def symlink(self,content,path):
        debug("symlink",content,path)
        # fs.checkdir(path)
        self.fs.symlink(content,path)
        debug("symlink returning")
        return 0

def main():
    usage="""ArchiveFS: an archival file system that stores only
    single copies of the same file.""" + fuse.Fuse.fusage

    server = ArchiveFS(version="%prog "+fuse.__version__,
                       usage=usage, dash_s_do='setsingle')
    server.parser.add_option(mountopt="root",metavar="PATH",default="/tmp/TEST",help="storage directory")
    server.parse(values=server,errex=1)
    server.flags = 0
    server.multithreaded = 0
    server.main()

if __name__ == '__main__':
    main()
