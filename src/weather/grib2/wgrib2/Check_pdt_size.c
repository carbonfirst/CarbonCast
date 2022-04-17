#include <stdio.h>
#include <stdlib.h>
#include "grb2.h"
#include "wgrib2.h"
#include "fnlist.h"

/*
 * HEADER:100:check_pdt_size:misc:1:check pdt size X=1 enable/default, X=0 disable
 */

int check_pdt_size_flag = 1;
int warn_check_pdt = 1;

int f_check_pdt_size(ARG1) {
   check_pdt_size_flag = atoi(arg1);
   return 0;
}

int check_pdt_size(unsigned char **sec) {
    int pdt_size, pdt, n, np, nc, nb;

    if (check_pdt_size_flag == 0) return 1;

    pdt = code_table_4_0(sec);
    pdt_size =  GB2_Sec4_size(sec);

    switch(pdt) {
    case 0: return pdt_size == 34;
    case 1: return pdt_size == 37;
    case 2: return pdt_size == 36;
    case 3: return pdt_size == 68 + sec[4][57];
    case 4: return pdt_size == 64 + sec[4][53];
    case 5: return pdt_size == 47;
    case 6: return pdt_size == 35;
    case 7: return pdt_size == 34;
    case 8: n = sec[4][41];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 46 + 12*n;
    case 9: n = sec[4][54];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 59 + 12*n;
    case 10: n = sec[4][42];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 47 + 12*n;
    case 11: n = sec[4][44];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 49 + 12*n;
    case 12: n = sec[4][43];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 48 + 12*n;
    case 13: n = sec[4][75];
    		nc = sec[4][57];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 80 + 12*n + nc;
    case 14: n = sec[4][71];
    		nc = sec[4][53];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 76 + 12*n + nc;
    case 15: return pdt_size == 37;
    case 20: return pdt_size == 43;
    case 30: nb = sec[4][13];
		return pdt_size == 14 + nb*10;
    case 31: nb = sec[4][13];
		return pdt_size == 14 + nb*11;
    case 32:
    case 33:
    case 34: nb = sec[4][22];
		return pdt_size == 23 + nb*11;
    case 35: nb = sec[4][14];
		return pdt_size == 15 + nb*11;
    case 40: return pdt_size == 36;
    case 41: return pdt_size == 39;
    case 42: n = sec[4][43];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 48 + 12*n;
    case 43: n = sec[4][46];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 51 + 12*n;
    case 44: return pdt_size == 45;
    case 45: return pdt_size == 50;
    case 46: n = sec[4][54];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 59 + 12*n;
    case 47: n = sec[4][57];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 62 + 12*n;
    case 48: return pdt_size == 58;
    case 49: return pdt_size == 61;
    case 51: nc = sec[4][34];
		return pdt_size == 35+12*nc;
    case 53: n = sec[4][12];
		return pdt_size == 38 + 2*n;
    case 54: n = sec[4][12];
		return pdt_size == 41 + 2*n;
    case 55: return pdt_size == 40;
    case 56: return pdt_size == 42;
    case 57: n = sec[4][19];
		return pdt_size == 43 + 5*n;
    case 58: n = sec[4][19];
		return pdt_size == 46 + 5*n;
    case 59: return pdt_size == 43;
    case 60: return pdt_size == 44;
    case 61: n = sec[4][51];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 56 + 12*n;
    case 62: n = sec[4][47];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 55 + 12*n;
    case 63: n = sec[4][50];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 55 + 12*n;
    case 67: 
		np = sec[4][19];
		n = sec[4][50+5*np];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 55 + 5*np + 12*n;
    case 68: 
		np = sec[4][19];
		n = sec[4][53+5*np];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 58 + 5*np + 12*n;
    case 70: return pdt_size == 39;
    case 71: return pdt_size == 42;
    case 72: n = sec[4][46];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 51 + 12*n;
    case 73: n = sec[4][49];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 54 + 12*n;
    case 91: 
		nc = sec[4][34];
		n = sec[4][54+12*(nc-1)];
		if (n == 0) return 0;	/* illegal time range */
		return pdt_size == 72 + 12*(n-1) + 12*(nc-1);
    case 254:   return pdt_size == 15;
    case 1000: return pdt_size == 22;	
    case 1001: return pdt_size == 38;	
    case 1002: return pdt_size == 35;	
    case 1100: return pdt_size == 34;	
    case 1101: return pdt_size == 50;

    default: 
	if (warn_check_pdt) fprintf(stderr,"*** Update check_pdt_size: pdt_size unknown, pdt=%d ***\n", pdt);
	warn_check_pdt = 0;
	return 1;
    }
    return 1;
}
