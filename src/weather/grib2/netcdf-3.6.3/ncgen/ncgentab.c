
# line 10 "ncgen.y"
#ifndef lint
static char SccsId[] = "$Id: ncgentab.c,v 1.18 2008/05/13 04:06:50 russ Exp $";
#endif
#include        <string.h>
#include	<stdlib.h>
#include	<netcdf.h>
#include 	"generic.h"
#include        "ncgen.h"
#include	"genlib.h"	/* for grow_darray() et al */

typedef struct Symbol {		/* symbol table entry */
	char    	*name;
	struct Symbol   *next;
	unsigned	is_dim : 1;	/* appears as netCDF dimension */
	unsigned	is_var : 1;	/* appears as netCDF variable */
	unsigned	is_att : 1;	/* appears as netCDF attribute */
	int             dnum;	        /* handle as a dimension */
	int             vnum;	        /* handle as a variable */
	} *YYSTYPE1;

/* True if string a equals string b*/
#define	STREQ(a, b)	(*(a) == *(b) && strcmp((a), (b)) == 0)
#define NC_UNSPECIFIED ((nc_type)0)	/* unspecified (as yet) type */

#define YYSTYPE YYSTYPE1
YYSTYPE symlist;		/* symbol table: linked list */

extern int derror_count;	/* counts errors in netcdf definition */
extern int lineno;		/* line number for error messages */

static int not_a_string;	/* whether last constant read was a string */
static char termstring[MAXTRST]; /* last terminal string read */
static double double_val;	/* last double value read */
static float float_val;		/* last float value read */
static int int_val;		/* last int value read */
static short short_val;		/* last short value read */
static char char_val;		/* last char value read */
static signed char byte_val;	/* last byte value read */

static nc_type type_code;	/* holds declared type for variables */
static nc_type atype_code;	/* holds derived type for attributes */
static char *netcdfname;	/* to construct netcdf file name */
static void *att_space;		/* pointer to block for attribute values */
static nc_type valtype;		/* type code for list of attribute values  */

static char *char_valp;		/* pointers used to accumulate data values */
static signed char *byte_valp;
static short *short_valp;
static int *int_valp;
static float *float_valp;
static double *double_valp;
static void *rec_cur;		/* pointer to where next data value goes */
static void *rec_start;		/* start of space for data */
# define NC_UNLIMITED_K 257
# define BYTE_K 258
# define CHAR_K 259
# define SHORT_K 260
# define INT_K 261
# define FLOAT_K 262
# define DOUBLE_K 263
# define IDENT 264
# define TERMSTRING 265
# define BYTE_CONST 266
# define CHAR_CONST 267
# define SHORT_CONST 268
# define INT_CONST 269
# define FLOAT_CONST 270
# define DOUBLE_CONST 271
# define DIMENSIONS 272
# define VARIABLES 273
# define NETCDF 274
# define DATA 275
# define FILLVALUE 276

#include <inttypes.h>

#ifdef __STDC__
#include <stdlib.h>
#include <string.h>
#define	YYCONST	const
#else
#include <malloc.h>
#include <memory.h>
#define	YYCONST
#endif


#if defined(__cplusplus) || defined(__STDC__)

#if defined(__cplusplus) && defined(__EXTERN_C__)
extern "C" {
#endif
#ifndef yyerror
#if defined(__cplusplus)
	void yyerror(YYCONST char *);
#endif
#endif
#ifndef yylex
	int yylex(void);
#endif
	int yyparse(void);
#if defined(__cplusplus) && defined(__EXTERN_C__)
}
#endif

#endif

#define yyclearin yychar = -1
#define yyerrok yyerrflag = 0
extern int yychar;
extern int yyerrflag;
#ifndef YYSTYPE
#define YYSTYPE int
#endif
YYSTYPE yylval;
YYSTYPE yyval;
typedef int yytabelem;
#ifndef YYMAXDEPTH
#define YYMAXDEPTH 150
#endif
#if YYMAXDEPTH > 0
int yy_yys[YYMAXDEPTH], *yys = yy_yys;
YYSTYPE yy_yyv[YYMAXDEPTH], *yyv = yy_yyv;
#else	/* user does initial allocation */
int *yys;
YYSTYPE *yyv;
#endif
static int yymaxdepth = YYMAXDEPTH;
# define YYERRCODE 256

# line 746 "ncgen.y"


/* HELPER PROGRAMS */
void defatt()
{
    valnum = 0;
    valtype = NC_UNSPECIFIED;
    /* get a large block for attributes, realloc later */
    att_space = emalloc(MAX_NC_ATTSIZE);
    /* make all kinds of pointers point to it */
    char_valp = (char *) att_space;
    byte_valp = (signed char *) att_space;
    short_valp = (short *) att_space;
    int_valp = (int *) att_space;
    float_valp = (float *) att_space;
    double_valp = (double *) att_space;
}

void equalatt()
{
    /* check if duplicate attribute for this var */
    int i;
    for(i=0; i<natts; i++) { /* expensive */
        if(atts[i].var == varnum &&
           STREQ(atts[i].name,atts[natts].name)) {
            derror("duplicate attribute %s:%s",
                   vars[varnum].name,atts[natts].name);
        }
    }
    atts[natts].var = varnum ;
    atts[natts].type = valtype;
    atts[natts].len = valnum;
    /* shrink space down to what was really needed */
    att_space = erealloc(att_space, valnum*nctypesize(valtype));
    atts[natts].val = att_space;
    if (STREQ(atts[natts].name, _FillValue) &&
        atts[natts].var != NC_GLOBAL) {
        nc_putfill(atts[natts].type,atts[natts].val,
                   &vars[atts[natts].var].fill_value);
        if(atts[natts].type != vars[atts[natts].var].type) {
            derror("variable %s: %s type mismatch",
                   vars[atts[natts].var].name, _FillValue);
        }
    }
    natts++;
}
/* PROGRAMS */

#ifdef vms
void
#else
int
#endif
yyerror(	/* called for yacc syntax error */
     char *s)
{
	derror(s);
#ifndef vms
	return -1;
#endif
}

/* undefine yywrap macro, in case we are using bison instead of yacc */
#ifdef yywrap
#undef yywrap
#endif

int
yywrap(void)			/* returns 1 on EOF if no more input */
{
    return  1;
}


/* Symbol table operations for ncgen tool */

YYSTYPE lookup(       /* find sname in symbol table (linear search) */
	const char *sname)
{
    YYSTYPE sp;
    for (sp = symlist; sp != (YYSTYPE) 0; sp = sp -> next)
	if (STREQ(sp -> name, sname)) {
	    return sp;
	}
    return 0;			/* 0 ==> not found */
}

YYSTYPE install(  /* install sname in symbol table */
	const char *sname)
{
    YYSTYPE sp;

    sp = (YYSTYPE) emalloc (sizeof (struct Symbol));
    sp -> name = (char *) emalloc (strlen (sname) + 1);/* +1 for '\0' */
    (void) strcpy (sp -> name, sname);
    sp -> next = symlist;	/* put at front of list */
    sp -> is_dim = 0;
    sp -> is_var = 0;
    sp -> is_att = 0;
    symlist = sp;
    return sp;
}

void
clearout(void)	/* reset symbol table to empty */
{
    YYSTYPE sp, tp;
    for (sp = symlist; sp != (YYSTYPE) 0;) {
	tp = sp -> next;
	free (sp -> name);
	free ((char *) sp);
	sp = tp;
    }
    symlist = 0;
}

/* get lexical input routine generated by lex  */
#include "ncgenyy.c"
static YYCONST yytabelem yyexca[] ={
-1, 1,
	0, -1,
	-2, 0,
	};
# define YYNPROD 79
# define YYLAST 231
static YYCONST yytabelem yyact[]={

   102,   103,   101,   104,   105,   106,   107,    46,    12,    60,
     2,   108,    74,    75,    73,    76,    77,    78,    79,    18,
     6,    58,    35,    59,    12,    40,    61,     3,    95,    71,
    17,    91,    70,    34,    33,    50,    63,    89,    68,    55,
    44,    43,    43,    88,    81,    65,    54,    48,    37,    53,
    12,    39,    97,    99,    87,    98,    56,    42,    66,    51,
    15,    85,    21,    14,    24,   100,    96,    94,    82,    62,
    10,    72,    38,    11,    36,    52,    26,    41,    90,    84,
    67,    64,    49,    47,    25,    23,    22,     9,    20,    16,
    13,    45,    19,     7,     5,     4,     1,    64,     0,    80,
    51,    86,    83,     0,    57,    69,     0,     0,     0,     0,
     0,     0,     0,     0,     0,     0,    92,    93,     0,     0,
     0,     0,     0,     0,     0,     0,     0,     0,   110,    92,
   109,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     0,     0,     0,     8,    27,    28,    29,    30,    31,    32,
    35 };
static YYCONST yytabelem yypact[]={

  -264,-10000000,   -96,-10000000,  -252,   -50,  -245,-10000000,   -34,    -8,
   -11,-10000000,  -239,  -245,    -2,-10000000,   -21,-10000000,-10000000,  -268,
   -34,   -12,-10000000,-10000000,-10000000,  -242,-10000000,-10000000,-10000000,-10000000,
-10000000,-10000000,-10000000,    -9,-10000000,-10000000,   -13,-10000000,   -22,-10000000,
-10000000,    -3,-10000000,  -245,  -248,   -99,  -242,   -14,-10000000,    14,
-10000000,-10000000,   -23,  -239,-10000000,  -253,-10000000,-10000000,-10000000,-10000000,
-10000000,-10000000,  -242,   -15,-10000000,-10000000,  -242,    21,  -253,-10000000,
    10,-10000000,-10000000,-10000000,-10000000,-10000000,-10000000,-10000000,-10000000,-10000000,
   -16,-10000000,   -24,-10000000,-10000000,  -245,    10,  -253,-10000000,-10000000,
    11,-10000000,-10000000,-10000000,     9,-10000000,  -265,-10000000,  -245,-10000000,
-10000000,-10000000,-10000000,-10000000,-10000000,-10000000,-10000000,-10000000,-10000000,-10000000,
-10000000 };
static YYCONST yytabelem yypgo[]={

     0,    96,    95,    94,    93,    92,    91,    90,    63,    60,
    89,    30,    88,    87,    62,    86,    85,    64,    84,    82,
    35,    33,    80,    79,    78,    31,    76,    75,    32,    73,
    72,    34,    51,    29,    71,    69,    36,    68,    67,    28,
    66,    65 };
static YYCONST yytabelem yyr1[]={

     0,     2,     5,     1,     3,     3,     7,     7,     8,     8,
     9,     9,     9,    10,    11,     4,     4,     4,    12,    12,
    14,    14,    14,    13,    13,    15,    18,    18,    18,    18,
    18,    18,    19,    19,    22,    20,    21,    23,    23,    24,
    24,    25,    27,    16,    30,    17,    26,    29,    31,    32,
    28,    28,    33,    34,    34,    34,    34,    34,    34,    34,
     6,     6,     6,    35,    35,    37,    36,    38,    38,    40,
    39,    41,    41,    41,    41,    41,    41,    41,    41 };
static YYCONST yytabelem yyr2[]={

     0,     1,     1,    17,     0,     4,     4,     6,     2,     6,
     7,     7,     7,     3,     2,     0,     4,     2,     4,     6,
     2,     2,     2,     4,     6,     4,     3,     3,     3,     3,
     3,     3,     2,     6,     1,     7,     2,     0,     6,     2,
     6,     3,     1,     9,     1,     9,     6,     5,     3,     3,
     2,     6,     3,     3,     3,     3,     3,     3,     3,     3,
     0,     4,     2,     4,     6,     1,     9,     2,     6,     1,
     5,     3,     3,     3,     3,     3,     3,     3,     3 };
static YYCONST yytabelem yychk[]={

-10000000,    -1,   274,   123,    -2,    -3,   272,    -4,   273,   -13,
   -17,   -29,    58,    -7,    -8,    -9,   -10,   -11,   264,    -5,
   -12,   -14,   -15,   -16,   -17,   -18,   -26,   258,   259,   260,
   261,   262,   263,   -31,   -21,   264,   -17,    59,   -30,   -32,
   264,    -8,    59,    44,    61,    -6,   275,   -14,    59,   -19,
   -20,   -21,   -27,    58,    59,    61,    59,    -9,   269,   271,
   257,   125,   -35,   -36,   -31,    59,    44,   -22,    61,   -32,
   -28,   -33,   -34,   267,   265,   266,   268,   269,   270,   271,
   -36,    59,   -37,   -20,   -23,    40,   -28,    44,    59,    61,
   -24,   -25,   -11,   -33,   -38,   -39,   -40,    41,    44,    44,
   -41,   267,   265,   266,   268,   269,   270,   271,   276,   -25,
   -39 };
static YYCONST yytabelem yydef[]={

     0,    -2,     0,     1,     4,    15,     0,     2,     0,    17,
     0,    44,     0,     5,     0,     8,     0,    13,    14,    60,
    16,     0,    20,    21,    22,     0,    42,    26,    27,    28,
    29,    30,    31,     0,    48,    36,     0,    23,     0,    47,
    49,     0,     6,     0,     0,     0,    62,     0,    18,    25,
    32,    34,     0,     0,    24,     0,     7,     9,    10,    11,
    12,     3,    61,     0,    65,    19,     0,    37,     0,    46,
    45,    50,    52,    53,    54,    55,    56,    57,    58,    59,
     0,    63,     0,    33,    35,     0,    43,     0,    64,    69,
     0,    39,    41,    51,    66,    67,     0,    38,     0,    69,
    70,    71,    72,    73,    74,    75,    76,    77,    78,    40,
    68 };
typedef struct
#ifdef __cplusplus
	yytoktype
#endif
{
#ifdef __cplusplus
const
#endif
char *t_name; int t_val; } yytoktype;
#ifndef YYDEBUG
#	define YYDEBUG	0	/* don't allow debugging */
#endif

#if YYDEBUG

yytoktype yytoks[] =
{
	"NC_UNLIMITED_K",	257,
	"BYTE_K",	258,
	"CHAR_K",	259,
	"SHORT_K",	260,
	"INT_K",	261,
	"FLOAT_K",	262,
	"DOUBLE_K",	263,
	"IDENT",	264,
	"TERMSTRING",	265,
	"BYTE_CONST",	266,
	"CHAR_CONST",	267,
	"SHORT_CONST",	268,
	"INT_CONST",	269,
	"FLOAT_CONST",	270,
	"DOUBLE_CONST",	271,
	"DIMENSIONS",	272,
	"VARIABLES",	273,
	"NETCDF",	274,
	"DATA",	275,
	"FILLVALUE",	276,
	"-unknown-",	-1	/* ends search */
};

#ifdef __cplusplus
const
#endif
char * yyreds[] =
{
	"-no such reduction-",
	"ncdesc : NETCDF '{'",
	"ncdesc : NETCDF '{' dimsection vasection",
	"ncdesc : NETCDF '{' dimsection vasection datasection '}'",
	"dimsection : /* empty */",
	"dimsection : DIMENSIONS dimdecls",
	"dimdecls : dimdecline ';'",
	"dimdecls : dimdecls dimdecline ';'",
	"dimdecline : dimdecl",
	"dimdecline : dimdecline ',' dimdecl",
	"dimdecl : dimd '=' INT_CONST",
	"dimdecl : dimd '=' DOUBLE_CONST",
	"dimdecl : dimd '=' NC_UNLIMITED_K",
	"dimd : dim",
	"dim : IDENT",
	"vasection : /* empty */",
	"vasection : VARIABLES vadecls",
	"vasection : gattdecls",
	"vadecls : vadecl ';'",
	"vadecls : vadecls vadecl ';'",
	"vadecl : vardecl",
	"vadecl : attdecl",
	"vadecl : gattdecl",
	"gattdecls : gattdecl ';'",
	"gattdecls : gattdecls gattdecl ';'",
	"vardecl : type varlist",
	"type : BYTE_K",
	"type : CHAR_K",
	"type : SHORT_K",
	"type : INT_K",
	"type : FLOAT_K",
	"type : DOUBLE_K",
	"varlist : varspec",
	"varlist : varlist ',' varspec",
	"varspec : var",
	"varspec : var dimspec",
	"var : IDENT",
	"dimspec : /* empty */",
	"dimspec : '(' dimlist ')'",
	"dimlist : vdim",
	"dimlist : dimlist ',' vdim",
	"vdim : dim",
	"attdecl : att",
	"attdecl : att '=' attvallist",
	"gattdecl : gatt",
	"gattdecl : gatt '=' attvallist",
	"att : avar ':' attr",
	"gatt : ':' attr",
	"avar : var",
	"attr : IDENT",
	"attvallist : aconst",
	"attvallist : attvallist ',' aconst",
	"aconst : attconst",
	"attconst : CHAR_CONST",
	"attconst : TERMSTRING",
	"attconst : BYTE_CONST",
	"attconst : SHORT_CONST",
	"attconst : INT_CONST",
	"attconst : FLOAT_CONST",
	"attconst : DOUBLE_CONST",
	"datasection : /* empty */",
	"datasection : DATA datadecls",
	"datasection : DATA",
	"datadecls : datadecl ';'",
	"datadecls : datadecls datadecl ';'",
	"datadecl : avar",
	"datadecl : avar '=' constlist",
	"constlist : dconst",
	"constlist : constlist ',' dconst",
	"dconst : /* empty */",
	"dconst : const",
	"const : CHAR_CONST",
	"const : TERMSTRING",
	"const : BYTE_CONST",
	"const : SHORT_CONST",
	"const : INT_CONST",
	"const : FLOAT_CONST",
	"const : DOUBLE_CONST",
	"const : FILLVALUE",
};
#endif /* YYDEBUG */
# line	1 "/usr/ccs/bin/yaccpar"
/*
 * Copyright (c) 1993 by Sun Microsystems, Inc.
 */

#pragma ident	"@(#)yaccpar	6.16	99/01/20 SMI"

/*
** Skeleton parser driver for yacc output
*/

/*
** yacc user known macros and defines
*/
#define YYERROR		goto yyerrlab
#define YYACCEPT	return(0)
#define YYABORT		return(1)
#define YYBACKUP( newtoken, newvalue )\
{\
	if ( yychar >= 0 || ( yyr2[ yytmp ] >> 1 ) != 1 )\
	{\
		yyerror( "syntax error - cannot backup" );\
		goto yyerrlab;\
	}\
	yychar = newtoken;\
	yystate = *yyps;\
	yylval = newvalue;\
	goto yynewstate;\
}
#define YYRECOVERING()	(!!yyerrflag)
#define YYNEW(type)	malloc(sizeof(type) * yynewmax)
#define YYCOPY(to, from, type) \
	(type *) memcpy(to, (char *) from, yymaxdepth * sizeof (type))
#define YYENLARGE( from, type) \
	(type *) realloc((char *) from, yynewmax * sizeof(type))
#ifndef YYDEBUG
#	define YYDEBUG	1	/* make debugging available */
#endif

/*
** user known globals
*/
int yydebug;			/* set to 1 to get debugging */

/*
** driver internal defines
*/
#define YYFLAG		(-10000000)

/*
** global variables used by the parser
*/
YYSTYPE *yypv;			/* top of value stack */
int *yyps;			/* top of state stack */

int yystate;			/* current state */
int yytmp;			/* extra var (lasts between blocks) */

int yynerrs;			/* number of errors */
int yyerrflag;			/* error recovery flag */
int yychar;			/* current input token number */



#ifdef YYNMBCHARS
#define YYLEX()		yycvtok(yylex())
/*
** yycvtok - return a token if i is a wchar_t value that exceeds 255.
**	If i<255, i itself is the token.  If i>255 but the neither 
**	of the 30th or 31st bit is on, i is already a token.
*/
#if defined(__STDC__) || defined(__cplusplus)
int yycvtok(int i)
#else
int yycvtok(i) int i;
#endif
{
	int first = 0;
	int last = YYNMBCHARS - 1;
	int mid;
	wchar_t j;

	if(i&0x60000000){/*Must convert to a token. */
		if( yymbchars[last].character < i ){
			return i;/*Giving up*/
		}
		while ((last>=first)&&(first>=0)) {/*Binary search loop*/
			mid = (first+last)/2;
			j = yymbchars[mid].character;
			if( j==i ){/*Found*/ 
				return yymbchars[mid].tvalue;
			}else if( j<i ){
				first = mid + 1;
			}else{
				last = mid -1;
			}
		}
		/*No entry in the table.*/
		return i;/* Giving up.*/
	}else{/* i is already a token. */
		return i;
	}
}
#else/*!YYNMBCHARS*/
#define YYLEX()		yylex()
#endif/*!YYNMBCHARS*/

/*
** yyparse - return 0 if worked, 1 if syntax error not recovered from
*/
#if defined(__STDC__) || defined(__cplusplus)
int yyparse(void)
#else
int yyparse()
#endif
{
	register YYSTYPE *yypvt = 0;	/* top of value stack for $vars */

#if defined(__cplusplus) || defined(lint)
/*
	hacks to please C++ and lint - goto's inside
	switch should never be executed
*/
	static int __yaccpar_lint_hack__ = 0;
	switch (__yaccpar_lint_hack__)
	{
		case 1: goto yyerrlab;
		case 2: goto yynewstate;
	}
#endif

	/*
	** Initialize externals - yyparse may be called more than once
	*/
	yypv = &yyv[-1];
	yyps = &yys[-1];
	yystate = 0;
	yytmp = 0;
	yynerrs = 0;
	yyerrflag = 0;
	yychar = -1;

#if YYMAXDEPTH <= 0
	if (yymaxdepth <= 0)
	{
		if ((yymaxdepth = YYEXPAND(0)) <= 0)
		{
			yyerror("yacc initialization error");
			YYABORT;
		}
	}
#endif

	{
		register YYSTYPE *yy_pv;	/* top of value stack */
		register int *yy_ps;		/* top of state stack */
		register int yy_state;		/* current state */
		register int  yy_n;		/* internal state number info */
	goto yystack;	/* moved from 6 lines above to here to please C++ */

		/*
		** get globals into registers.
		** branch to here only if YYBACKUP was called.
		*/
	yynewstate:
		yy_pv = yypv;
		yy_ps = yyps;
		yy_state = yystate;
		goto yy_newstate;

		/*
		** get globals into registers.
		** either we just started, or we just finished a reduction
		*/
	yystack:
		yy_pv = yypv;
		yy_ps = yyps;
		yy_state = yystate;

		/*
		** top of for (;;) loop while no reductions done
		*/
	yy_stack:
		/*
		** put a state and value onto the stacks
		*/
#if YYDEBUG
		/*
		** if debugging, look up token value in list of value vs.
		** name pairs.  0 and negative (-1) are special values.
		** Note: linear search is used since time is not a real
		** consideration while debugging.
		*/
		if ( yydebug )
		{
			register int yy_i;

			printf( "State %d, token ", yy_state );
			if ( yychar == 0 )
				printf( "end-of-file\n" );
			else if ( yychar < 0 )
				printf( "-none-\n" );
			else
			{
				for ( yy_i = 0; yytoks[yy_i].t_val >= 0;
					yy_i++ )
				{
					if ( yytoks[yy_i].t_val == yychar )
						break;
				}
				printf( "%s\n", yytoks[yy_i].t_name );
			}
		}
#endif /* YYDEBUG */
		if ( ++yy_ps >= &yys[ yymaxdepth ] )	/* room on stack? */
		{
			/*
			** reallocate and recover.  Note that pointers
			** have to be reset, or bad things will happen
			*/
			long yyps_index = (yy_ps - yys);
			long yypv_index = (yy_pv - yyv);
			long yypvt_index = (yypvt - yyv);
			int yynewmax;
#ifdef YYEXPAND
			yynewmax = YYEXPAND(yymaxdepth);
#else
			yynewmax = 2 * yymaxdepth;	/* double table size */
			if (yymaxdepth == YYMAXDEPTH)	/* first time growth */
			{
				char *newyys = (char *)YYNEW(int);
				char *newyyv = (char *)YYNEW(YYSTYPE);
				if (newyys != 0 && newyyv != 0)
				{
					yys = YYCOPY(newyys, yys, int);
					yyv = YYCOPY(newyyv, yyv, YYSTYPE);
				}
				else
					yynewmax = 0;	/* failed */
			}
			else				/* not first time */
			{
				yys = YYENLARGE(yys, int);
				yyv = YYENLARGE(yyv, YYSTYPE);
				if (yys == 0 || yyv == 0)
					yynewmax = 0;	/* failed */
			}
#endif
			if (yynewmax <= yymaxdepth)	/* tables not expanded */
			{
				yyerror( "yacc stack overflow" );
				YYABORT;
			}
			yymaxdepth = yynewmax;

			yy_ps = yys + yyps_index;
			yy_pv = yyv + yypv_index;
			yypvt = yyv + yypvt_index;
		}
		*yy_ps = yy_state;
		*++yy_pv = yyval;

		/*
		** we have a new state - find out what to do
		*/
	yy_newstate:
		if ( ( yy_n = yypact[ yy_state ] ) <= YYFLAG )
			goto yydefault;		/* simple state */
#if YYDEBUG
		/*
		** if debugging, need to mark whether new token grabbed
		*/
		yytmp = yychar < 0;
#endif
		if ( ( yychar < 0 ) && ( ( yychar = YYLEX() ) < 0 ) )
			yychar = 0;		/* reached EOF */
#if YYDEBUG
		if ( yydebug && yytmp )
		{
			register int yy_i;

			printf( "Received token " );
			if ( yychar == 0 )
				printf( "end-of-file\n" );
			else if ( yychar < 0 )
				printf( "-none-\n" );
			else
			{
				for ( yy_i = 0; yytoks[yy_i].t_val >= 0;
					yy_i++ )
				{
					if ( yytoks[yy_i].t_val == yychar )
						break;
				}
				printf( "%s\n", yytoks[yy_i].t_name );
			}
		}
#endif /* YYDEBUG */
		if ( ( ( yy_n += yychar ) < 0 ) || ( yy_n >= YYLAST ) )
			goto yydefault;
		if ( yychk[ yy_n = yyact[ yy_n ] ] == yychar )	/*valid shift*/
		{
			yychar = -1;
			yyval = yylval;
			yy_state = yy_n;
			if ( yyerrflag > 0 )
				yyerrflag--;
			goto yy_stack;
		}

	yydefault:
		if ( ( yy_n = yydef[ yy_state ] ) == -2 )
		{
#if YYDEBUG
			yytmp = yychar < 0;
#endif
			if ( ( yychar < 0 ) && ( ( yychar = YYLEX() ) < 0 ) )
				yychar = 0;		/* reached EOF */
#if YYDEBUG
			if ( yydebug && yytmp )
			{
				register int yy_i;

				printf( "Received token " );
				if ( yychar == 0 )
					printf( "end-of-file\n" );
				else if ( yychar < 0 )
					printf( "-none-\n" );
				else
				{
					for ( yy_i = 0;
						yytoks[yy_i].t_val >= 0;
						yy_i++ )
					{
						if ( yytoks[yy_i].t_val
							== yychar )
						{
							break;
						}
					}
					printf( "%s\n", yytoks[yy_i].t_name );
				}
			}
#endif /* YYDEBUG */
			/*
			** look through exception table
			*/
			{
				register YYCONST int *yyxi = yyexca;

				while ( ( *yyxi != -1 ) ||
					( yyxi[1] != yy_state ) )
				{
					yyxi += 2;
				}
				while ( ( *(yyxi += 2) >= 0 ) &&
					( *yyxi != yychar ) )
					;
				if ( ( yy_n = yyxi[1] ) < 0 )
					YYACCEPT;
			}
		}

		/*
		** check for syntax error
		*/
		if ( yy_n == 0 )	/* have an error */
		{
			/* no worry about speed here! */
			switch ( yyerrflag )
			{
			case 0:		/* new error */
				yyerror( "syntax error" );
				goto skip_init;
			yyerrlab:
				/*
				** get globals into registers.
				** we have a user generated syntax type error
				*/
				yy_pv = yypv;
				yy_ps = yyps;
				yy_state = yystate;
			skip_init:
				yynerrs++;
				/* FALLTHRU */
			case 1:
			case 2:		/* incompletely recovered error */
					/* try again... */
				yyerrflag = 3;
				/*
				** find state where "error" is a legal
				** shift action
				*/
				while ( yy_ps >= yys )
				{
					yy_n = yypact[ *yy_ps ] + YYERRCODE;
					if ( yy_n >= 0 && yy_n < YYLAST &&
						yychk[yyact[yy_n]] == YYERRCODE)					{
						/*
						** simulate shift of "error"
						*/
						yy_state = yyact[ yy_n ];
						goto yy_stack;
					}
					/*
					** current state has no shift on
					** "error", pop stack
					*/
#if YYDEBUG
#	define _POP_ "Error recovery pops state %d, uncovers state %d\n"
					if ( yydebug )
						printf( _POP_, *yy_ps,
							yy_ps[-1] );
#	undef _POP_
#endif
					yy_ps--;
					yy_pv--;
				}
				/*
				** there is no state on stack with "error" as
				** a valid shift.  give up.
				*/
				YYABORT;
			case 3:		/* no shift yet; eat a token */
#if YYDEBUG
				/*
				** if debugging, look up token in list of
				** pairs.  0 and negative shouldn't occur,
				** but since timing doesn't matter when
				** debugging, it doesn't hurt to leave the
				** tests here.
				*/
				if ( yydebug )
				{
					register int yy_i;

					printf( "Error recovery discards " );
					if ( yychar == 0 )
						printf( "token end-of-file\n" );
					else if ( yychar < 0 )
						printf( "token -none-\n" );
					else
					{
						for ( yy_i = 0;
							yytoks[yy_i].t_val >= 0;
							yy_i++ )
						{
							if ( yytoks[yy_i].t_val
								== yychar )
							{
								break;
							}
						}
						printf( "token %s\n",
							yytoks[yy_i].t_name );
					}
				}
#endif /* YYDEBUG */
				if ( yychar == 0 )	/* reached EOF. quit */
					YYABORT;
				yychar = -1;
				goto yy_newstate;
			}
		}/* end if ( yy_n == 0 ) */
		/*
		** reduction by production yy_n
		** put stack tops, etc. so things right after switch
		*/
#if YYDEBUG
		/*
		** if debugging, print the string that is the user's
		** specification of the reduction which is just about
		** to be done.
		*/
		if ( yydebug )
			printf( "Reduce by (%d) \"%s\"\n",
				yy_n, yyreds[ yy_n ] );
#endif
		yytmp = yy_n;			/* value to switch over */
		yypvt = yy_pv;			/* $vars top of value stack */
		/*
		** Look in goto table for next state
		** Sorry about using yy_state here as temporary
		** register variable, but why not, if it works...
		** If yyr2[ yy_n ] doesn't have the low order bit
		** set, then there is no action to be done for
		** this reduction.  So, no saving & unsaving of
		** registers done.  The only difference between the
		** code just after the if and the body of the if is
		** the goto yy_stack in the body.  This way the test
		** can be made before the choice of what to do is needed.
		*/
		{
			/* length of production doubled with extra bit */
			register int yy_len = yyr2[ yy_n ];

			if ( !( yy_len & 01 ) )
			{
				yy_len >>= 1;
				yyval = ( yy_pv -= yy_len )[1];	/* $$ = $1 */
				yy_state = yypgo[ yy_n = yyr1[ yy_n ] ] +
					*( yy_ps -= yy_len ) + 1;
				if ( yy_state >= YYLAST ||
					yychk[ yy_state =
					yyact[ yy_state ] ] != -yy_n )
				{
					yy_state = yyact[ yypgo[ yy_n ] ];
				}
				goto yy_stack;
			}
			yy_len >>= 1;
			yyval = ( yy_pv -= yy_len )[1];	/* $$ = $1 */
			yy_state = yypgo[ yy_n = yyr1[ yy_n ] ] +
				*( yy_ps -= yy_len ) + 1;
			if ( yy_state >= YYLAST ||
				yychk[ yy_state = yyact[ yy_state ] ] != -yy_n )
			{
				yy_state = yyact[ yypgo[ yy_n ] ];
			}
		}
					/* save until reenter driver code */
		yystate = yy_state;
		yyps = yy_ps;
		yypv = yy_pv;
	}
	/*
	** code supplied by user is placed in this switch
	*/
	switch( yytmp )
	{
		
case 1:
# line 97 "ncgen.y"
{ init_netcdf(); } break;
case 2:
# line 100 "ncgen.y"
{
		       if (derror_count == 0)
			 define_netcdf(netcdfname);
		       if (derror_count > 0)
			   exit(6);
		   } break;
case 3:
# line 108 "ncgen.y"
{
		       if (derror_count == 0)
			 close_netcdf();
		   } break;
case 10:
# line 123 "ncgen.y"
{ if (int_val <= 0)
			 derror("dimension length must be positive");
		     dims[ndims].size = int_val;
		     ndims++;
		   } break;
case 11:
# line 129 "ncgen.y"
{ /* for rare case where 2^31 < dimsize < 2^32 */
		       if (double_val <= 0)
			 derror("dimension length must be positive");
		       if (double_val > 4294967295.0)
			 derror("dimension too large");
		       if (double_val - (size_t) double_val > 0)
			 derror("dimension length must be an integer");
		       dims[ndims].size = (size_t) double_val;
		       ndims++;
                   } break;
case 12:
# line 140 "ncgen.y"
{  if (rec_dim != -1)
			 derror("only one NC_UNLIMITED dimension allowed");
		     rec_dim = ndims; /* the unlimited (record) dimension */
		     dims[ndims].size = NC_UNLIMITED;
		     ndims++;
		   } break;
case 13:
# line 148 "ncgen.y"
{ 
		    deescapify(yypvt[-0]->name); /* delete escape chars from names, 
					     e.g. 'ab\:cd\ ef' to 'ab:cd ef' */
		    if (yypvt[-0]->is_dim == 1) {
		        derror( "duplicate dimension declaration for %s",
		                yypvt[-0]->name);
		     }
	             yypvt[-0]->is_dim = 1;
		     yypvt[-0]->dnum = ndims;
		     /* make sure dims array will hold dimensions */
		     grow_darray(ndims,  /* must hold ndims+1 dims */
				 &dims); /* grow as needed */
		     dims[ndims].name = (char *) emalloc(strlen(yypvt[-0]->name)+1);
		     (void) strcpy(dims[ndims].name, yypvt[-0]->name);
		     /* name for use in generated Fortran and C variables */
		     dims[ndims].lname = decodify(yypvt[-0]->name);
		   } break;
case 26:
# line 182 "ncgen.y"
{ type_code = NC_BYTE; } break;
case 27:
# line 183 "ncgen.y"
{ type_code = NC_CHAR; } break;
case 28:
# line 184 "ncgen.y"
{ type_code = NC_SHORT; } break;
case 29:
# line 185 "ncgen.y"
{ type_code = NC_INT; } break;
case 30:
# line 186 "ncgen.y"
{ type_code = NC_FLOAT; } break;
case 31:
# line 187 "ncgen.y"
{ type_code = NC_DOUBLE; } break;
case 34:
# line 193 "ncgen.y"
{
		    static struct vars dummyvar;

		    dummyvar.name = "dummy";
		    dummyvar.type = NC_DOUBLE;
		    dummyvar.ndims = 0;
		    dummyvar.dims = 0;
		    dummyvar.fill_value.doublev = NC_FILL_DOUBLE;
		    dummyvar.has_data = 0;

		    nvdims = 0;
		    deescapify(yypvt[-0]->name);   /* delete escape chars from names, 
					     e.g. 'ab\:cd\ ef' to 'ab:cd ef' */
		    /* make sure variable not re-declared */
		    if (yypvt[-0]->is_var == 1) {
		       derror( "duplicate variable declaration for %s",
		               yypvt[-0]->name);
		    }
	            yypvt[-0]->is_var = 1;
		    yypvt[-0]->vnum = nvars;
		    /* make sure vars array will hold variables */
		    grow_varray(nvars,  /* must hold nvars+1 vars */
				&vars); /* grow as needed */
		    vars[nvars] = dummyvar; /* to make Purify happy */
		    vars[nvars].name = (char *) emalloc(strlen(yypvt[-0]->name)+1);
		    (void) strcpy(vars[nvars].name, yypvt[-0]->name);
		    /* name for use in generated Fortran and C variables */
		    vars[nvars].lname = decodify(yypvt[-0]->name);
		    vars[nvars].type = type_code;
		    /* set default fill value.  You can override this with
		     * the variable attribute "_FillValue". */
		    nc_getfill(type_code, &vars[nvars].fill_value);
		    vars[nvars].has_data = 0; /* has no data (yet) */
		   } break;
case 35:
# line 228 "ncgen.y"
{
		    vars[nvars].ndims = nvdims;
		    nvars++;
		   } break;
case 41:
# line 242 "ncgen.y"
{
		    if (nvdims >= NC_MAX_VAR_DIMS) {
		       derror("%s has too many dimensions",vars[nvars].name);
		    }
		    if (yypvt[-0]->is_dim == 1)
		       dimnum = yypvt[-0]->dnum;
		    else {
		       derror( "%s is not declared as a dimension",
			       yypvt[-0]->name);
	               dimnum = ndims;
		    }
		    if (rec_dim != -1 && dimnum == rec_dim && nvdims != 0) {
		       derror("unlimited dimension must be first");
		    }
		    grow_iarray(nvdims, /* must hold nvdims+1 ints */
				&vars[nvars].dims); /* grow as needed */
		    vars[nvars].dims[nvdims] = dimnum;
                    nvdims++;
		   } break;
case 42:
# line 263 "ncgen.y"
{
                   defatt();
		   } break;
case 43:
# line 267 "ncgen.y"
{
                   equalatt();
		   } break;
case 44:
# line 272 "ncgen.y"
{
                   defatt();
		   } break;
case 45:
# line 276 "ncgen.y"
{
                   equalatt();
		   } break;
case 47:
# line 284 "ncgen.y"
{
		    varnum = NC_GLOBAL;  /* handle of "global" attribute */
		   } break;
case 48:
# line 290 "ncgen.y"
{ if (yypvt[-0]->is_var == 1)
		       varnum = yypvt[-0]->vnum;
		    else {
		      derror("%s not declared as a variable, fatal error",
			     yypvt[-0]->name);
		      YYABORT;
		      }
		   } break;
case 49:
# line 300 "ncgen.y"
{
		       /* make sure atts array will hold attributes */
		       grow_aarray(natts,  /* must hold natts+1 atts */
				   &atts); /* grow as needed */
		       deescapify(yypvt[-0]->name); /* delete escape chars from names, 
						e.g. 'ab\:cd\ ef' to 'ab:cd ef' */
		       atts[natts].name = (char *) emalloc(strlen(yypvt[-0]->name)+1);
		       (void) strcpy(atts[natts].name,yypvt[-0]->name);
		       /* name for use in generated Fortran and C variables */
		       atts[natts].lname = decodify(yypvt[-0]->name);
		   } break;
case 52:
# line 316 "ncgen.y"
{
		    if (valtype == NC_UNSPECIFIED)
		      valtype = atype_code;
		    if (valtype != atype_code)
		      derror("values for attribute must be all of same type");
		   } break;
case 53:
# line 325 "ncgen.y"
{
		       atype_code = NC_CHAR;
		       *char_valp++ = char_val;
		       valnum++;
		   } break;
case 54:
# line 331 "ncgen.y"
{
		       atype_code = NC_CHAR;
		       {
			   /* don't null-terminate attribute strings */
			   size_t len = strlen(termstring);
			   if (len == 0) /* need null if that's only value */
			       len = 1;
			   (void)strncpy(char_valp,termstring,len);
			   valnum += len;
			   char_valp += len;
		       }
		   } break;
case 55:
# line 344 "ncgen.y"
{
		       atype_code = NC_BYTE;
		       *byte_valp++ = byte_val;
		       valnum++;
		   } break;
case 56:
# line 350 "ncgen.y"
{
		       atype_code = NC_SHORT;
		       *short_valp++ = short_val;
		       valnum++;
		   } break;
case 57:
# line 356 "ncgen.y"
{
		       atype_code = NC_INT;
		       *int_valp++ = int_val;
		       valnum++;
		   } break;
case 58:
# line 362 "ncgen.y"
{
		       atype_code = NC_FLOAT;
		       *float_valp++ = float_val;
		       valnum++;
		   } break;
case 59:
# line 368 "ncgen.y"
{
		       atype_code = NC_DOUBLE;
		       *double_valp++ = double_val;
		       valnum++;
		   } break;
case 65:
# line 384 "ncgen.y"
{
		       valtype = vars[varnum].type; /* variable type */
		       valnum = 0;	/* values accumulated for variable */
		       vars[varnum].has_data = 1;
		       /* compute dimensions product */
		       var_size = nctypesize(valtype);
		       if (vars[varnum].ndims == 0) { /* scalar */
			   var_len = 1;
		       } else if (vars[varnum].dims[0] == rec_dim) {
			   var_len = 1; /* one record for unlimited vars */
		       } else {
			   var_len = dims[vars[varnum].dims[0]].size;
		       }
		       for(dimnum = 1; dimnum < vars[varnum].ndims; dimnum++)
			 var_len = var_len*dims[vars[varnum].dims[dimnum]].size;
		       /* allocate memory for variable data */
		       if (var_len*var_size != (size_t)(var_len*var_size)) {
			   derror("variable %s too large for memory",
				  vars[varnum].name);
			   exit(9);
		       }
		       rec_len = var_len;
		       rec_start = malloc ((size_t)(rec_len*var_size));
		       if (rec_start == 0) {
			   derror ("out of memory\n");
			   exit(3);
		       }
		       rec_cur = rec_start;
		       switch (valtype) {
			 case NC_CHAR:
			   char_valp = (char *) rec_start;
			   break;
			 case NC_BYTE:
			   byte_valp = (signed char *) rec_start;
			   break;
			 case NC_SHORT:
			   short_valp = (short *) rec_start;
			   break;
			 case NC_INT:
			   int_valp = (int *) rec_start;
			   break;
			 case NC_FLOAT:
			   float_valp = (float *) rec_start;
			   break;
			 case NC_DOUBLE:
			   double_valp = (double *) rec_start;
			   break;
		       }
		 } break;
case 66:
# line 434 "ncgen.y"
{
		       if (valnum < var_len) { /* leftovers */
			   nc_fill(valtype,
				    var_len - valnum,
				    rec_cur,
				    vars[varnum].fill_value);
		       }
		       /* put out var_len values */
		       /* vars[varnum].nrecs = valnum / rec_len; */
		       vars[varnum].nrecs = var_len / rec_len;
		       if (derror_count == 0)
			   put_variable(rec_start);
		       free ((char *) rec_start);
		 } break;
case 69:
# line 453 "ncgen.y"
{
		       if(valnum >= var_len) {
			   if (vars[varnum].dims[0] != rec_dim) { /* not recvar */
			       derror("too many values for this variable, %d >= %d",
				      valnum, var_len);
			       exit (4);
			   } else { /* a record variable, so grow data
				      container and increment var_len by
				      multiple of record size */
			       ptrdiff_t rec_inc = (char *)rec_cur
				   - (char *)rec_start;
			       var_len = rec_len * (1 + valnum / rec_len);
			       rec_start = erealloc(rec_start, var_len*var_size);
			       rec_cur = (char *)rec_start + rec_inc;
			       char_valp = (char *) rec_cur;
			       byte_valp = (signed char *) rec_cur;
			       short_valp = (short *) rec_cur;
			       int_valp = (int *) rec_cur;
			       float_valp = (float *) rec_cur;
			       double_valp = (double *) rec_cur;
			   }
		       }
		       not_a_string = 1;
                   } break;
case 70:
# line 478 "ncgen.y"
{
		       if (not_a_string) {
			   switch (valtype) {
			     case NC_CHAR:
			       rec_cur = (void *) char_valp;
			       break;
			     case NC_BYTE:
			       rec_cur = (void *) byte_valp;
			       break;
			     case NC_SHORT:
			       rec_cur = (void *) short_valp;
			       break;
			     case NC_INT:
			       rec_cur = (void *) int_valp;
			       break;
			     case NC_FLOAT:
			       rec_cur = (void *) float_valp;
			       break;
			     case NC_DOUBLE:
			       rec_cur = (void *) double_valp;
			       break;
			   }
		       }
		   } break;
case 71:
# line 505 "ncgen.y"
{
		       atype_code = NC_CHAR;
		       switch (valtype) {
			 case NC_CHAR:
			   *char_valp++ = char_val;
			   break;
			 case NC_BYTE:
			   *byte_valp++ = char_val;
			   break;
			 case NC_SHORT:
			   *short_valp++ = char_val;
			   break;
			 case NC_INT:
			   *int_valp++ = char_val;
			   break;
			 case NC_FLOAT:
			   *float_valp++ = char_val;
			   break;
			 case NC_DOUBLE:
			   *double_valp++ = char_val;
			   break;
		       }
		       valnum++;
		   } break;
case 72:
# line 530 "ncgen.y"
{
		       not_a_string = 0;
		       atype_code = NC_CHAR;
		       {
			   size_t len = strlen(termstring);

			   if(valnum + len > var_len) {
			       if (vars[varnum].dims[0] != rec_dim) {
				   derror("too many values for this variable, %d>%d", 
					  valnum+len, var_len);
				   exit (5);
			       } else {/* a record variable so grow it */
				   ptrdiff_t rec_inc = (char *)rec_cur
				       - (char *)rec_start;
				   var_len += rec_len * (len + valnum - var_len)/rec_len;
				   rec_start = erealloc(rec_start, var_len*var_size);
				   rec_cur = (char *)rec_start + rec_inc;
				   char_valp = (char *) rec_cur;
			       }
			   }
			   switch (valtype) {
			     case NC_CHAR:
			       {
				   int ld;
				   size_t i, sl;
				   (void)strncpy(char_valp,termstring,len);
				   ld = vars[varnum].ndims-1;
				   if (ld > 0) {/* null-fill to size of last dim */
				       sl = dims[vars[varnum].dims[ld]].size;
				       for (i =len;i<sl;i++)
					   char_valp[i] = '\0';
				       if (sl < len)
					   sl = len;
				       valnum += sl;
				       char_valp += sl;
				   } else { /* scalar or 1D strings */
				       valnum += len;
				       char_valp += len;
				   }
				   rec_cur = (void *) char_valp;
			       }
			       break;
			     case NC_BYTE:
			     case NC_SHORT:
			     case NC_INT:
			     case NC_FLOAT:
			     case NC_DOUBLE:
			       derror("string value invalid for %s variable",
				      nctype(valtype));
			       break;
			   }
		       }
		   } break;
case 73:
# line 584 "ncgen.y"
{
		       atype_code = NC_BYTE;
		       switch (valtype) {
			 case NC_CHAR:
			   *char_valp++ = byte_val;
			   break;
			 case NC_BYTE:
			   *byte_valp++ = byte_val;
			   break;
			 case NC_SHORT:
			   *short_valp++ = byte_val;
			   break;
			 case NC_INT:
			   *int_valp++ = byte_val;
			   break;
			 case NC_FLOAT:
			   *float_valp++ = byte_val;
			   break;
			 case NC_DOUBLE:
			   *double_valp++ = byte_val;
			   break;
		       }
		       valnum++;
		   } break;
case 74:
# line 609 "ncgen.y"
{
		       atype_code = NC_SHORT;
		       switch (valtype) {
			 case NC_CHAR:
			   *char_valp++ = short_val;
			   break;
			 case NC_BYTE:
			   *byte_valp++ = short_val;
			   break;
			 case NC_SHORT:
			   *short_valp++ = short_val;
			   break;
			 case NC_INT:
			   *int_valp++ = short_val;
			   break;
			 case NC_FLOAT:
			   *float_valp++ = short_val;
			   break;
			 case NC_DOUBLE:
			   *double_valp++ = short_val;
			   break;
		       }
		       valnum++;
		   } break;
case 75:
# line 634 "ncgen.y"
{
		       atype_code = NC_INT;
		       switch (valtype) {
			 case NC_CHAR:
			   *char_valp++ = int_val;
			   break;
			 case NC_BYTE:
			   *byte_valp++ = int_val;
			   break;
			 case NC_SHORT:
			   *short_valp++ = int_val;
			   break;
			 case NC_INT:
			   *int_valp++ = int_val;
			   break;
			 case NC_FLOAT:
			   *float_valp++ = int_val;
			   break;
			 case NC_DOUBLE:
			   *double_valp++ = int_val;
			   break;
		       }
		       valnum++;
		   } break;
case 76:
# line 659 "ncgen.y"
{
		       atype_code = NC_FLOAT;
		       switch (valtype) {
			 case NC_CHAR:
			   *char_valp++ = float_val;
			   break;
			 case NC_BYTE:
			   *byte_valp++ = float_val;
			   break;
			 case NC_SHORT:
			   *short_valp++ = float_val;
			   break;
			 case NC_INT:
			   *int_valp++ = float_val;
			   break;
			 case NC_FLOAT:
			   *float_valp++ = float_val;
			   break;
			 case NC_DOUBLE:
			   *double_valp++ = float_val;
			   break;
		       }
		       valnum++;
		   } break;
case 77:
# line 684 "ncgen.y"
{
		       atype_code = NC_DOUBLE;
		       switch (valtype) {
			 case NC_CHAR:
			   *char_valp++ = double_val;
			   break;
			 case NC_BYTE:
			   *byte_valp++ = double_val;
			   break;
			 case NC_SHORT:
			   *short_valp++ = double_val;
			   break;
			 case NC_INT:
			   *int_valp++ = double_val;
			   break;
			 case NC_FLOAT:
			   if (double_val == NC_FILL_DOUBLE)
			     *float_valp++ = NC_FILL_FLOAT;
			   else
			     *float_valp++ = double_val;
			   break;
			 case NC_DOUBLE:
			   *double_valp++ = double_val;
			   break;
		       }
		       valnum++;
		   } break;
case 78:
# line 712 "ncgen.y"
{
		       /* store fill_value */
		       switch (valtype) {
		       case NC_CHAR:
			   nc_fill(valtype, 1, (void *)char_valp++,
				   vars[varnum].fill_value);
			   break;
		       case NC_BYTE:
			   nc_fill(valtype, 1, (void *)byte_valp++,
				   vars[varnum].fill_value);
			   break;
		       case NC_SHORT:
			   nc_fill(valtype, 1, (void *)short_valp++,
				   vars[varnum].fill_value);
			   break;
		       case NC_INT:
			   nc_fill(valtype, 1, (void *)int_valp++,
				   vars[varnum].fill_value);
			   break;
		       case NC_FLOAT:
			   nc_fill(valtype, 1, (void *)float_valp++,
				   vars[varnum].fill_value);
			   break;
		       case NC_DOUBLE:
			   nc_fill(valtype, 1, (void *)double_valp++,
				   vars[varnum].fill_value);
			   break;
		       }
		       valnum++;
		   } break;
# line	531 "/usr/ccs/bin/yaccpar"
	}
	goto yystack;		/* reset registers in driver code */
}

