
set key off
set pm3d
set view map
set size square
unset surface
#unset colorbox
natoms=666667.0
xc_array = 100.0
yc_array = 100.0
half_xwidth=125.00
half_ywidth=125.00
set xlabel "X (micrometers)"
set ylabel "Y (micrometers)"
set xtics xc_array*10.0-half_xwidth,50.0,xc_array*10.0+half_xwidth
set ytics yc_array*10.0-half_ywidth,50.0,yc_array*10.0+half_ywidth
#set ztics -0.25,0.05,0.25
set xrange [xc_array*10.0-half_xwidth:xc_array*10.0+half_xwidth]
set yrange [yc_array*10.0-half_ywidth:yc_array*10.0+half_ywidth]
#set xrange [-24:24]
#set yrange [-24:24]
#set zrange [-0.25:0.25]
set cbrange [0.0:20000.0]
#set palette defined (0.0 '#00007f', 0.1 '#0000b1', 0.2 '#0000e8', \
#                     0.3 '#0028ff', 0.4 '#0080ff', 0.5 '#00c8ff', \
#                     0.6 '#15ffe1', 0.7 '#bdff39', 0.8 '#ff3b00', \
#                     0.9 '#c80000', 1.0 '#7f0000')
#
# set palette for NIST colormap
#
set palette defined (0.000 '#000080', 0.110 '#0000FF', 0.125 '#0000FF', \
                     0.340 '#00DBFF', 0.350 '#00E6F7', 0.375 '#14FFE2', \
                     0.640 '#EEFF08', 0.650 '#F7F600', 0.660 '#FFEC00', \
                     0.890 '#FF1300', 0.910 '#E80000', 1.000 '#800000')
set term gif
do for [i=0:329] {
set term gif
set output sprintf("density_distribution_%03d.gif",i)
set title sprintf("time = %03d ms",i)
splot sprintf("wf_ascii_%03d.dat",i) u (($1)*10.0):(($2)*10.0):(($3*$3+$4*$4)*natoms) w l}

