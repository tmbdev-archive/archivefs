#include <sys/types.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <fcntl.h>

int main(int argc,char **argv) {
    int fd,n,bad,i;
    const char *result = "  02 05        15  19    25   ";
    char buf[10000];
    fd = creat("test-seek.out",0777);
    write(fd,"                              ",30);
    lseek(fd,5,SEEK_SET);
    write(fd,"05",2);
    lseek(fd,15,SEEK_SET);
    write(fd,"15",2);
    lseek(fd,25,SEEK_SET);
    write(fd,"25",2);
    lseek(fd,2,SEEK_SET);
    write(fd,"02",2);
    lseek(fd,19,SEEK_SET);
    write(fd,"19",2);
    close(fd);
    fd = open("test-seek.out",O_RDONLY);
    n = read(fd,buf,sizeof buf);
    buf[n]==0;
    bad = 0;
    for(i=0;i<n;i++) {
        if(result[i]!=buf[i]) {
            printf("%2d: %d %d\n",i,result[i],buf[i]);
            bad = 0;
        }
    }
    if(bad>0) {
        printf("%d bad characters\n",bad);
        exit(1);
    } else {
        exit(0);
    }
}

