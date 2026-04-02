cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c          program split-step, Crank-Nicolson Gross-Pitaevskii Solver          c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      program rrhp_2d_gpe_solver
      implicit none
c
c This program solves the 2D Gross-Pitaevskii equation (GPE) using the 
c split-step, Crank-Nicolson (SSCN) algorithm.  This program reads one
c input file: General Inputs.  It has the capability of integrating in 
c either real or imaginary time.
c
c Mark Edwards, Thu Feb 12 14:23:19 EST 2015 
c
c	declare array_max
c
      integer*4 a_max
c
c	parameter a_max = max value of array declarations
c
      parameter(a_max=1000)
c	begin: input declarations
      real*8 dx, dy, dt, g_bar, tfi, tff, L0, Natoms
      integer*4 Nx, Ny, Nt, Nframes, real_or_imag, read_initial_wf
      integer*4 output_frames, phase_imprint
      integer*4 diag_stride
c	end: input declarations
      real*8  x(0:a_max),  y(0:a_max) !space-grid arrays
      real*8 x2(0:a_max), y2(0:a_max) !squares of space-grid arrays
      real*8 V(0:a_max,0:a_max)       !potential array
      integer*4 i, j, k, n, frame_counter, ix, iy
      real*8 delta_tf, tc, tfc, optden
      character*80 counter_string
      character*12 f1
      character*16 filename
ccccc adding code to output wave function cuts
      character*80 cutfilename
ccccc finished code to output wave function cuts
c
c	begin: Crank-Nicolson parameter declarations
c	NOTE: all variables that start with a "c" are declared complex*16
c
      complex*16 ci                                    !square-root of -1
      complex*16 cA2x, cA2x0, cA2y, cA2y0
      complex*16 calpha2x(0:a_max), cgamma2x(0:a_max)
      complex*16 calpha2y(0:a_max), cgamma2y(0:a_max)
      complex*16 cPsi(0:a_max,0:a_max)
      complex*16 cdtdx2, cdtdy2
ccccc adding declarations for unformatted output
      real*8 WFR(0:a_max,0:a_max), WFI(0:a_max,0:a_max)
ccccc finished declations for unformatted output
c       begin potential parameters declarations
c      real*8 x01, y01, r01, theta1, nu_r1
c      real*8 x02, y02, r02, theta2, nu_r2
c      real*8 a, Ubmax, nu_max, tramp_si, ton_si
      real*8 rho, density, phi, pi, step, w1, w2
      real*8 psir(0:a_max,0:a_max), psii(0:a_max,0:a_max)
      real*8 thc, atom_mass, hbar, E0, T0
      real*8 tc_si, omega_max, rot_angle_calc
cccc begin dissipation declarations cccc
      integer*4 with_diss
      real*8 gamma_diss
cccc end dissipation declarations cccc
      real*8 mu
cccc begin phase jumps declarations cccc
      integer*4 Npts
      real*8 pj1, pj2
      real*8 omega_rf
c	begin: dtap declarations
      real*8 V0, a, wd, wr, nn, R
      integer*4 nrows, ncols
      real*8 xc_array, yc_array, wperp, wpara
      real*8 Ubmax(1:100,1:100)
      real*8 tramp_si, ton_si
      real*8 Vt(0:a_max,0:a_max)
      real*8 wn_array(1:100,1:2) !winding number array
      real*8 x1c, y1c, x2c, y2c, tpi_si, trel_si
c	end: dtap declarations
      integer*4 irow, icol, iw
c
c       begin: timing instrumentation declarations
c
      integer*8 t_start, t_end, count_rate, count_max
      real*8 time_potential, time_nu, time_luxrf, time_luyrf
      real*8 time_normalize, time_io, time_diag, time_total
      real*8 time_loop_start, time_loop_end
c
c       end: timing instrumentation declarations
c
c       end potential parameters declarations
c
c	get General Inputs
c	
      call read_general_inputs(Natoms,
     +                         Nx,
     +                         Ny,
     +                         dx,
     +                         dy,
     +                         g_bar,
     +                         Nt,
     +                         dt,
     +                         Nframes,
     +                         tfi,
     +                         tff,
     +                         L0,
     +                         real_or_imag,
     +                         read_initial_wf,
     +                         output_frames,
     +                         phase_imprint,
     +                         with_diss,
     +                         gamma_diss,
     +                         omega_rf,
     +                         diag_stride)
cccc
cccc	print General Inputs for debug
cccc
      print *, "         General Inputs "
      print *, "Nx              = ", Nx
      print *, "Ny              = ", Ny
      print *, "dx              = ", dx
      print *, "dy              = ", dy
      print *, "g_bar           = ", g_bar
      print *, "Nt              = ", Nt
      print *, "dt              = ", dt
      print *, "Nframes         = ", Nframes
      print *, "tfi             = ", tfi
      print *, "tff             = ", tff
      print *, "L0              = ", L0
      print *, "real_or_imag    = ", real_or_imag
      print *, "read_initial_wf = ", read_initial_wf
      print *, "output_frames   = ", output_frames
      print *, "phase_imprint   = ", phase_imprint
      print *, "with_diss       = ", with_diss
      print *, "gamma_diss      = ", gamma_diss
      print *, "omega_rf        = ", omega_rf
      print *, "diag_stride     = ", diag_stride
ccc      pause
c
c	read parameter values
c
      call get_dtap_inputs(V0,
     +                     a,
     +                     wd,
     +                     wr,
     +                     R,
     +                     nn,
     +                     nrows,
     +                     ncols,
     +                     xc_array,
     +                     yc_array,
     +                     wperp,
     +                     wpara,
     +                     Ubmax,
     +                     tramp_si,
     +                     ton_si,
     +                     tpi_si,
     +                     trel_si)
c
c	print input values for debug
c
      print *
      print *, "V0       = ", V0
      print *, "a        = ", a
      print *, "wd       = ", wd
      print *, "wr       = ", wr
      print *, "R        = ", R
      print *, "nn       = ", nn
      print *, "nrows    = ", nrows
      print *, "ncols    = ", ncols
      print *, "xc_array = ", xc_array
      print *, "yc_array = ", yc_array
      print *, "wperp    = ", wperp
      print *, "wpara    = ", wpara
      do irow = 1, nrows
        write(6,*) (Ubmax(irow,icol), icol = 1, ncols)
      enddo
      print *, "tramp_si = ", tramp_si
      print *, "ton_si   = ", ton_si
      print *, "tpi_si   = ", tpi_si
      print *, "trel_si  = ", trel_si
ccc      pause
c
c       define scaled units parameters
c
      pi        = 3.1415926535897932d0
      atom_mass = 23.d0*1.66d-27
      hbar      = 1.0546d-34
      E0        = hbar*hbar/(2.d0*atom_mass*L0*L0)
      T0        = 2.d0*atom_mass*L0*L0/hbar
c
c       convert the rotating-frame speed from rad/sec to scaled units
c
      omega_rf = T0*omega_rf
c
c	compute the Crank-Nicolson coefficients
c
      call compute_CN_coefficients(a_max,
     +                             real_or_imag,
     +                             Nx,
     +                             Ny,
     +                             dx,
     +                             dy,
     +                             dt,
     +                             ci,
     +                             cA2x,
     +                             cA2x0,
     +                             calpha2x,
     +                             cgamma2x,
     +                             cA2y,
     +                             cA2y0,
     +                             calpha2y,
     +                             cgamma2y,
     +                             cdtdx2,
     +                             cdtdy2,
     +                             with_diss,
     +                             gamma_diss)
c
c	get initial wave function
c
      call get_initial_wf(xc_array,
     +                    yc_array,
     +                    read_initial_wf,
     +                    real_or_imag,
     +                    a_max,
     +                    Nx,
     +                    Ny,
     +                    dx,
     +                    dy,
     +                    x,
     +                    y,
     +                    cPsi)
c
c       compute the potential
c
      call get_potential(a_max,V0,a,wd,wr,nn,R,
     +                   nrows,ncols,xc_array,yc_array,
     +                   wperp,wpara,Ubmax,tramp_si,
     +                   ton_si,tpi_si,trel_si,
     +                   Nx,Ny,x,y,tc_si,V,real_or_imag)
c
c       compute mu of initial state
c
      call get_mu(a_max,
     +            Nx,
     +            Ny,
     +            dx,
     +            dy,
     +            x,
     +            y,
     +            V,
     +            cPsi,
     +            g_bar,
     +            Natoms,
     +            mu)
      print *, "mu = ", mu
ccc      pause
c
c	open file to output wf before phase imprint
c
          open(unit=889,
     +         file="initial_wf_ascii_no_pi.dat",
     +         status="unknown")
c
c	separate complex wf into real and imag parts
c
          do i = 0, Nx
            do j = 0, Ny
              WFR(i,j) = dreal(cPsi(i,j))
              WFI(i,j) = dimag(cPsi(i,j))
              write(889,*) x(i), y(j), WFR(i,j), WFI(i,j)
            enddo
            write(889,*)
          enddo
c
c	close output file
c
          close(889)
c
c       apply circulation to initial wf if appropriate
c
      call apply_phase_imprint(a_max,
     +                         nrows,
     +                         ncols,
     +                         xc_array,
     +                         yc_array,
     +                         R,
     +                         wr,
     +                         Nx,
     +                         Ny,
     +                         x,
     +                         y,
     +                         real_or_imag,
     +                         phase_imprint,
     +                         cPsi)
c
c	open file to output wf
c
          open(unit=888,
     +         file="initial_wf_ascii.dat",
     +         status="unknown")
c
c	separate complex wf into real and imag parts
c
          do i = 0, Nx
            do j = 0, Ny
              WFR(i,j) = dreal(cPsi(i,j))
              WFI(i,j) = dimag(cPsi(i,j))
              write(888,*) x(i), y(j), WFR(i,j), WFI(i,j)
            enddo
            write(888,*)
          enddo
c
c	close output file
c
          close(888)
ccc          pause
c
c        and write to file for debug
c
      open(unit=44,
     +     file="initial_pot.dat",
     +     status="unknown")
c
      do ix = 0, Nx
        do iy = 0, Ny
          write(44,*) x(ix), y(iy), V(ix,iy)
        enddo
        write(44,*)
      enddo
c
      close(44)
c
c	initialize frame_counter and delta_tf
c
      delta_tf      = (tff-tfi)/dfloat(Nframes)
      frame_counter = 0
      tfc           = 0.d0
c
c	initialize current time, tc
c
      tc = 0.d0
c
c       open "circulation.dat" for circulation output
c
      open(unit=171,
     +     file="circulation.dat",
     +     status="unknown")
c
c       open "phase_jumps.dat" for phase jumps output
c
ccc      open(unit=172,
ccc     +     file="phase_jumps.dat",
ccc     +     status="unknown")
cccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                  c
c       Initialize timing counters                 c
c                                                  c
cccccccccccccccccccccccccccccccccccccccccccccccccccc
      call system_clock(count_rate=count_rate, count_max=count_max)
      time_potential = 0.d0
      time_nu = 0.d0
      time_luxrf = 0.d0
      time_luyrf = 0.d0
      time_normalize = 0.d0
      time_io = 0.d0
      time_diag = 0.d0
      call system_clock(t_start)
      time_loop_start = dble(t_start)
cccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                  c
c       OpenACC: Copy data to GPU before time loop c
c       Data stays on GPU for duration of loop     c
c       Use !$acc update to sync with CPU for I/O  c
c                                                  c
cccccccccccccccccccccccccccccccccccccccccccccccccccc
!$acc data copy(cPsi, V) copyin(x, y)
cccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                  c
c	BEGIN time-propagation loop                c
c                                                  c
cccccccccccccccccccccccccccccccccccccccccccccccccccc
      do n = 1, Nt
c
c	if-block - output wf if tc <= tfc < tc+dt
c
        if (
     +      ((tc.le.tfc).AND.(tfc.lt.tc+dt))
     +  .AND.
     +      (output_frames.eq.1)) then
c
c       START I/O timing
c
          call system_clock(t_start)
c
c       OpenACC: Update cPsi from GPU to CPU for I/O
c
!$acc update self(cPsi)
c
c	create name of output file to open
c
          write(counter_string,"(I3.3)") frame_counter
          f1 = "wf_ascii_"//counter_string
          filename=f1//".dat"
ccc          print *, filename
ccc          pause
c
c	open file to output wf
c
          open(unit=555,
     +         file=filename,
     +         status="unknown")
c
c	separate complex wf into real and imag parts
c
          do i = 0, Nx
            do j = 0, Ny
              WFR(i,j) = dreal(cPsi(i,j))
              WFI(i,j) = dimag(cPsi(i,j))
              write(555,*) x(i), y(j), WFR(i,j), WFI(i,j)
            enddo
            write(555,*)
          enddo
c
c	close output file
c
          close(555)
c
c	update frame_counter and tfc
c
          frame_counter = frame_counter+1
          tfc           = tfc + delta_tf
c
c       END I/O timing
c
          call system_clock(t_end)
          time_io = time_io + dble(t_end-t_start)/dble(count_rate)
c
c	end if-block
c
        endif
c
c       START get_potential timing
c
        call system_clock(t_start)
c
c	update the potential array
c
      call get_potential(a_max,V0,a,wd,wr,nn,R,
     +                   nrows,ncols,xc_array,yc_array,
     +                   wperp,wpara,Ubmax,tramp_si,
     +                   ton_si,tpi_si,trel_si,
     +                   Nx,Ny,x,y,tc_si,V,real_or_imag)
c
c       if running with dissipation, subtract mu from V
c
        if (with_diss.eq.1) then
          do ix = 0, Nx
            do iy = 0, Ny
              V(ix,iy) = V(ix,iy) - mu
            enddo
          enddo
        endif
c
c       END get_potential timing
c
        call system_clock(t_end)
        time_potential = time_potential + dble(t_end-t_start)/
     +                   dble(count_rate)
c
c       START NU timing
c
        call system_clock(t_start)
c
c	compute psi_(k+1/3) = exp(-i*H1*dt)*psi_(k)
c
        call NU(a_max,
     +          real_or_imag,
     +          ci,
     +          dt,
     +          V,
     +          g_bar,
     +          Natoms,
     +          Nx,
     +          Ny,
     +          cPsi)
c
c       END NU timing
c
        call system_clock(t_end)
        time_nu = time_nu + dble(t_end-t_start)/dble(count_rate)
c
c       START LUXRF timing
c
        call system_clock(t_start)
c
c	compute psi_(k+2/3) = exp(-i*H2*dt)*psi_(k+1/3)
c
        call LUXRF(a_max,
     +             real_or_imag,
     +             Nx,
     +             Ny,
     +             dx,
     +             dy,
     +             dt,
     +             x,
     +             y,
     +             with_diss,
     +             gamma_diss,
     +             omega_rf,
     +             cPsi)
c
c       END LUXRF timing
c
        call system_clock(t_end)
        time_luxrf = time_luxrf + dble(t_end-t_start)/dble(count_rate)
ccc
ccc        call LUX(a_max,
ccc     +           Nx,
ccc     +           Ny,
ccc     +           cA2x,
ccc     +           cA2x0,
ccc     +           calpha2x,
ccc     +           cgamma2x,
ccc     +           cPsi)
c
c       START LUYRF timing
c
        call system_clock(t_start)
c
c	compute psi_(k+1) = exp(-i*H3*dt)*psi_(k+2/3)
c
        call LUYRF(a_max,
     +             real_or_imag,
     +             Nx,
     +             Ny,
     +             dx,
     +             dy,
     +             dt,
     +             x,
     +             y,
     +             with_diss,
     +             gamma_diss,
     +             omega_rf,
     +             cPsi)
c
c       END LUYRF timing
c
        call system_clock(t_end)
        time_luyrf = time_luyrf + dble(t_end-t_start)/dble(count_rate)
ccc
ccc        call LUY(a_max,
ccc     +           Nx,
ccc     +           Ny,
ccc     +           cA2y,
ccc     +           cA2y0,
ccc     +           calpha2y,
ccc     +           cgamma2y,
ccc     +           cPsi)
ccc
c
c	if-block: normalize cPsi if propagating in imaginary time
c
        if (real_or_imag.eq.0) then
c
c       START normalize_wf timing
c
          call system_clock(t_start)
c
c	normalize cPsi
c
          call normalize_wf(a_max,
     +                      Nx,
     +                      Ny,
     +                      dx,
     +                      dy,
     +                      cPsi)
c
c       END normalize_wf timing
c
          call system_clock(t_end)
          time_normalize = time_normalize + dble(t_end-t_start)/
     +                     dble(count_rate)
c
c	end if-block
c
        endif
c
c	update current time
c
        tc = tc + dt
cccccccccccccccccccccccccccccccccccccccccccccc
c                                            c
c           BEGIN: diagnostics (strided)     c
c    diag_stride > 0: compute every N steps  c
c    diag_stride <= 0: skip diagnostics      c
c                                            c
cccccccccccccccccccccccccccccccccccccccccccccc
        if ((diag_stride.gt.0).AND.(mod(n,diag_stride).eq.0)) then
c
c       START diagnostics timing
c
          call system_clock(t_start)
cccccccccccccccccccccccccccccccccccccccccccccc
c                                            c
c           BEGIN: circulation code          c
c                                            c
cccccccccccccccccccccccccccccccccccccccccccccc
c
c       fill psir and psii arrays
c
        do ix = 0, Nx
          do iy = 0, Ny
            psir(ix,iy) = dreal(cPsi(ix,iy))
            psii(ix,iy) = dimag(cPsi(ix,iy))
          enddo
        enddo
c
c	begin loops over array rings
c
        do irow = 1, nrows
          do icol = 1, ncols
c
c	compute center coordinates of ring 1
c
            x1c = xc_array + 
     +            (icol-0.5d0*dfloat(ncols+1))*(3.d0*R)
            y1c = yc_array + 
     +            (irow-0.5d0*dfloat(nrows+1))*(5.d0*R) + R
c
c       get circulation for ring 1 (ring with initial circulation)
c
            call get_winding_number(a_max,
     +                              x1c,
     +                              y1c,
     +                              R,
     +                              Nx,
     +                              Ny,
     +                              x,
     +                              y,
     +                              dx,
     +                              dy,
     +                              psir,
     +                              psii,
     +                              xc_array,
     +                              yc_array,
     +                              w1)
c
c	fill winding number array
c
            wn_array((irow-1)*ncols+icol,1) = w1
c
c	compute center coordinates of ring 2
c
            x2c = xc_array + 
     +            (icol-0.5d0*dfloat(ncols+1))*(3.d0*R)
            y2c = yc_array + 
     +            (irow-0.5d0*dfloat(nrows+1))*(5.d0*R) - R
c
c       get circulation for ring 2
c
            call get_winding_number(a_max,
     +                              x2c,
     +                              y2c,
     +                              R,
     +                              Nx,
     +                              Ny,
     +                              x,
     +                              y,
     +                              dx,
     +                              dy,
     +                              psir,
     +                              psii,
     +                              xc_array,
     +                              yc_array,
     +                              w2)
c
c	fill winding number array
c
            wn_array((irow-1)*ncols+icol,2) = w2
c
c	end loops over array rings
c
          enddo
        enddo
c
c       output circulations to file
c
        write(171,*) tc, (wn_array(iw,1), wn_array(iw,2), 
     +                    iw = 1, nrows*ncols)
cccccccccccccccccccccccccccccccccccccccccccccc
c                                            c
c           END: circulation code            c
c                                            c
cccccccccccccccccccccccccccccccccccccccccccccc
c
c       convert the current time to SI units
c
        if (real_or_imag.eq.0) then
          tc_si = 0.d0 !if integrating in imaginary time, set tc_si=0
        else
          tc_si     = tc*T0 !current time in seconds
        endif
c
c       END diagnostics timing
c
          call system_clock(t_end)
          time_diag = time_diag + dble(t_end-t_start)/dble(count_rate)
c
c       end diag_stride if-block
c
        endif
cccc
cccc	DEBUG: print progress to screen
cccc
        print *, "Finished time step ", n
cccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                  c
c	END time-propagation loop                  c
c                                                  c
cccccccccccccccccccccccccccccccccccccccccccccccccccc
      enddo
!$acc end data
c
c       Compute total loop time and print timing summary
c
      call system_clock(t_end)
      time_loop_end = dble(t_end)
      time_total = (time_loop_end - time_loop_start)/dble(count_rate)
c
      print *, " "
      print *, "============================================"
      print *, "         TIMING PROFILE SUMMARY             "
      print *, "============================================"
      print *, "Total time loop:     ", time_total, " seconds"
      print *, "--------------------------------------------"
      print *, "get_potential:       ", time_potential, " seconds"
      print *, "NU (nonlinear):      ", time_nu, " seconds"
      print *, "LUXRF (tridiag X):   ", time_luxrf, " seconds"
      print *, "LUYRF (tridiag Y):   ", time_luyrf, " seconds"
      print *, "normalize_wf:        ", time_normalize, " seconds"
      print *, "I/O (frame output):  ", time_io, " seconds"
      print *, "Diagnostics:         ", time_diag, " seconds"
      print *, "--------------------------------------------"
      print *, "Tridiag total:       ", time_luxrf+time_luyrf," seconds"
      print *, "============================================"
      print *, "          PERCENTAGE BREAKDOWN              "
      print *, "============================================"
      if (time_total.gt.0.d0) then
        print *, "get_potential:       ", 
     +           100.d0*time_potential/time_total, " %"
        print *, "NU (nonlinear):      ", 
     +           100.d0*time_nu/time_total, " %"
        print *, "LUXRF (tridiag X):   ", 
     +           100.d0*time_luxrf/time_total, " %"
        print *, "LUYRF (tridiag Y):   ", 
     +           100.d0*time_luyrf/time_total, " %"
        print *, "normalize_wf:        ", 
     +           100.d0*time_normalize/time_total, " %"
        print *, "I/O (frame output):  ", 
     +           100.d0*time_io/time_total, " %"
        print *, "Diagnostics:         ", 
     +           100.d0*time_diag/time_total, " %"
        print *, "--------------------------------------------"
        print *, "Tridiag total:       ", 
     +           100.d0*(time_luxrf+time_luyrf)/time_total, " %"
      endif
      print *, "============================================"
      print *, " "
c
c       close "circulation.dat" output file
c
      close(171)
c
c        and write to file for debug
c
      open(unit=45,
     +     file="final_pot.dat",
     +     status="unknown")
c
      do ix = 0, Nx
        do iy = 0, Ny
          write(45,*) x(ix), y(iy), V(ix,iy)
        enddo
        write(45,*)
      enddo
c
      close(45)
c
c	write final wf to file
c
      open(unit=777,
     +     file="final_wf.dat",
     +     status="unknown",
     +     form="unformatted")
c
c	separate complex wf into real and imag parts
c
      do i = 0, Nx
        do j = 0, Ny
          WFR(i,j) = dreal(cPsi(i,j))
          WFI(i,j) = dimag(cPsi(i,j))
        enddo
      enddo
c
c       write wf to binary file
c
      write(777) x, y, WFR, WFI
c
c       close final wf file
c    
      close(777)
c
c	end program
c
      stop
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                      subroutine apply_phase_imprint                          c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine apply_phase_imprint(a_max,
     +                               nrows,
     +                               ncols,
     +                               xc_array,
     +                               yc_array,
     +                               R,
     +                               wr,
     +                               Nx,
     +                               Ny,
     +                               x,
     +                               y,
     +                               real_or_imag,
     +                               phase_imprint,
     +                               cPsi)
      implicit none
      integer*4 a_max
      integer*4 nrows, ncols, icol, irow
      integer*4 Nx, Ny, ix, iy
      integer*4 real_or_imag, phase_imprint
      real*8 xc_array, yc_array, R, wr, phi, rho
      real*8 xc(1:100), yc(1:100), pi
      real*8 xcpi, ycpi, xrel, yrel
      real*8 x(0:a_max), y(0:a_max)
      complex*16 cPsi(0:a_max,0:a_max)
c
c This routine applies a phase imprint to the top-ring of each double-target
c potential BEC.
c
c	test for (real_or_imag.ne.1).OR.(phase_imprint.ne.1)
c
      if ((real_or_imag.ne.1).OR.(phase_imprint.ne.1)) then
        return
      endif
c
c	define pi
c
      pi = 3.1415926535897932d0
c
c	fill center arrays
c
      do icol = 1, ncols
        xc(icol) = xc_array + (icol-0.5d0*dfloat(ncols+1))*(3.d0*R)
      enddo
      do irow = 1, nrows
        yc(irow) = yc_array + (irow-0.5d0*dfloat(nrows+1))*(5.d0*R)
      enddo
c
c	begin loops over members of the double-target array
c
      do irow = 1, nrows
        do icol = 1, ncols
c
c	compute the center coordinates of current ring to
c	be phase-imprinted
c
          xcpi = xc(icol)
          ycpi = yc(irow) + R
c
c	begin loops over space grid to imprint current ring
c
          do ix = 0, Nx
            do iy = 0, Ny
              rho = dsqrt((x(ix)-xcpi)*(x(ix)-xcpi) +
     +                    (y(iy)-ycpi)*(y(iy)-ycpi))
c
c	compute current point relative to ring center
c
              xrel = x(ix)-xcpi
              yrel = y(iy)-ycpi
c     
c	begin add code to imprint only in the ring part of the upper
c	target potential
c
              if ((rho.ge.R-wr).AND.(rho.le.R+wr)) then
                if     ((xrel.gt.0.d0).AND.(yrel.gt.0.d0)) then
                  phi = 0.0d0*pi + datan(dabs(yrel/xrel))
                elseif ((xrel.lt.0.d0).AND.(yrel.gt.0.d0)) then
                  phi = 0.5d0*pi + datan(dabs(xrel/yrel))
                elseif ((xrel.lt.0.d0).AND.(yrel.lt.0.d0)) then
                  phi = 1.0d0*pi + datan(dabs(yrel/xrel))
                elseif ((xrel.gt.0.d0).AND.(yrel.lt.0.d0)) then
                  phi = 1.5d0*pi + datan(dabs(xrel/yrel))
                elseif ((xrel.eq.0.d0).AND.(yrel.gt.0.d0)) then
                  phi = 0.5d0*pi
                elseif ((xrel.eq.0.d0).AND.(yrel.lt.0.d0)) then
                  phi = 1.5d0*pi
                elseif ((xrel.gt.0.d0).AND.(yrel.eq.0.d0)) then
                  phi = 0.0d0*pi
                elseif ((xrel.lt.0.d0).AND.(yrel.eq.0.d0)) then
                  phi = 1.0d0*pi
                else
                  phi = 0.d0
                endif
              else
                phi = 0.d0
              endif
c     
c	end add code to imprint only in the ring part of the upper
c	target potential
c              
              if (rho.le.1.5d0*R) then
                cPsi(ix,iy) = cPsi(ix,iy)*cdexp((0.d0,1.d0)*phi)
              endif
c
c	end loops over space grid
c
            enddo
          enddo
c
c	end loops over members of the double-target array
c
        enddo
      enddo
c
c	return
c
      return
      end


cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                        subroutine get_phase_jumps                            c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine get_phase_jumps(a_max,
     +                           x01,y01,r01,
     +                           x02,y02,r02,
     +                           Npts,
     +                           Nx,
     +                           Ny,
     +                           dx,
     +                           dy,
     +                           x,
     +                           y,
     +                           WFR,
     +                           WFI,
     +                           pj1,
     +                           pj2)
      implicit none
      integer*4 a_max
      integer*4 ix, iy, Npts, i, j
      integer*4 Nx, Ny
      real*8 dx, dy, pi
      real*8 x01, y01, r01, x02, y02, r02
      real*8 x(0:a_max),  y(0:a_max) !space-grid arrays
      real*8 WFR(0:a_max,0:a_max), WFI(0:a_max,0:a_max)
      real*8 ring_pts1x(0:1024), ring_pts1y(0:1024)
      real*8 ring_pts2x(0:1024), ring_pts2y(0:1024)
      real*8 wfrs_ring1(0:1024), wfis_ring1(0:1024)
      real*8 wfrs_ring2(0:1024), wfis_ring2(0:1024)
      real*8 angles(0:1024), wfinterp
      real*8 ops1(0:1024), nps1(0:1024)
      real*8 ops2(0:1024), nps2(0:1024)
      real*8 pj1, pj2
c
c This routine computes the phase jumps around the two rings by unwrapping the
c wf phase around the midline track of each ring.
c
c
c       compute the midline-track points 
c
      pi = 3.1415926535897932d0
      do i = 0, Npts
        angles(i)     = dfloat(i)*(2.d0*pi/dfloat(Npts))
        ring_pts1x(i) = x01 + r01*dcos(angles(i))
        ring_pts1y(i) = y01 + r01*dsin(angles(i))
        ring_pts2x(i) = x02 + r02*dcos(angles(i))
        ring_pts2y(i) = y02 + r02*dsin(angles(i))
      enddo
c
c       compute interpolated wf value at midline-track points
c
      do i = 0, Npts
c
c  compute indexes of LL box corner for point i
c
        ix = int(ring_pts1x(i)/dx) + Nx/2
        iy = int(ring_pts1y(i)/dy) + Ny/2
c
        wfrs_ring1(i) = wfinterp(x(ix),x(ix+1),y(iy),y(iy+1),
     +                           WFR(ix,iy),WFR(ix,iy+1),
     +                           WFR(ix+1,iy),WFR(ix+1,iy+1),
     +                           ring_pts1x(i),ring_pts1y(i))
c
        wfis_ring1(i) = wfinterp(x(ix),x(ix+1),y(iy),y(iy+1),
     +                           WFI(ix,iy),WFI(ix,iy+1),
     +                           WFI(ix+1,iy),WFI(ix+1,iy+1),
     +                           ring_pts1x(i),ring_pts1y(i))
c
        ix = int(ring_pts2x(i)/dx) + Nx/2
        iy = int(ring_pts2y(i)/dy) + Ny/2
c
        wfrs_ring2(i) = wfinterp(x(ix),x(ix+1),y(iy),y(iy+1),
     +                           WFR(ix,iy),WFR(ix,iy+1),
     +                           WFR(ix+1,iy),WFR(ix+1,iy+1),
     +                           ring_pts2x(i),ring_pts2y(i))
c
        wfis_ring2(i) = wfinterp(x(ix),x(ix+1),y(iy),y(iy+1),
     +                           WFI(ix,iy),WFI(ix,iy+1),
     +                           WFI(ix+1,iy),WFI(ix+1,iy+1),
     +                           ring_pts2x(i),ring_pts2y(i))
      enddo
c
c             compute phase jump around the two rings
c
      call compute_pj(Npts,
     +                wfrs_ring1,
     +                wfis_ring1,
     +                pj1,
     +                ops1,
     +                nps1)
c
      call compute_pj(Npts,
     +                wfrs_ring2,
     +                wfis_ring2,
     +                pj2,
     +                ops2,
     +                nps2)
c
c       end program
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                           subroutine compute_pj                              c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine compute_pj(Npts,
     +                      psibr,
     +                      psibi,
     +                      pj,
     +                      old_phases,
     +                      new_phases)
      implicit none
      integer*4 Npts, i, pcounter
      real*8 psibr(0:1024), psibi(0:1024)
      real*8 phases(0:1024), arg, pj, pi
      real*8 old_phases(0:1024), new_phases(0:1024)
c
c This routine computes the phase jump around the point x(ix), y(iy) and returns.
c
c       define pi
c
      pi = 3.1415926535897932d0
c
c       computes old_phases
c
      do i = 0, Npts
        old_phases(i) = arg(psibr(i),psibi(i))
        phases(i)     = old_phases(i)
      enddo
c
c       compute the phases of the 8 points surrounding ix,iy
c
cccc      do i = 1, Npts
cccc        if (dabs(phases(i)-phases(i-1)).ge.1.0d0*pi) then
cccc          if (phases(i).gt.phases(i-1)) then
cccc            phases(i) = phases(i) - 2.d0*pi
cccc          elseif (phases(i).lt.phases(i-1)) then
cccc            phases(i) = phases(i) + 2.d0*pi
cccc          endif
cccc        endif
cccc      enddo
c
c       compute the phases of the 8 points surrounding ix,iy
c
      do i = 1, Npts
        if (dabs(phases(i)-phases(i-1)).ge.pi) then
          if (phases(i).gt.phases(i-1)) then
 777        phases(i) = phases(i) - 2.d0*pi
            if (dabs(phases(i)-phases(i-1)).ge.1.0d0*pi) goto 777
          elseif (phases(i).lt.phases(i-1)) then
 888        phases(i) = phases(i) + 2.d0*pi
            if (dabs(phases(i)-phases(i-1)).ge.1.0d0*pi) goto 888
          endif
        endif
      enddo
c
c       save new_phases
c
      do i = 0, Npts
        new_phases(i) = phases(i)
      enddo
c
c       compute pj
c
cccc      print *, phases(Npts), phases(0)
      pj = (phases(Npts)-phases(0))/(2.d0*pi)
c
c       return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                            subroutine wfinterp                               c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      real*8 function wfinterp(xlo,xhi,ylo,yhi,
     +                         wflolo,wflohi,
     +                         wfhilo,wfhihi,
     +                         x,y)
      implicit none
      real*8 xlo, xhi, ylo, yhi, x, y
      real*8 wflolo, wflohi, wfhilo, wfhihi
      real*8 area
c
c This function compute the bilinear interpolated value of the wf at the given
c point (x,y).  This point is bounded by a 2d box like this
c
c           + (xlo,yhi)       + (xhi,yhi)
c
c                      o (x,y)
c
c
c
c
c           + (xlo,ylo)       + (xhi,ylo)
c
c The wf value at the 4 corners are given and the interpolated value at
c (x,y) is returned.
c
c       compute the area
c
      area = (xhi-xlo)*(yhi-ylo)
c
c       compute the interpolated value
c
      wfinterp = wflolo*(xhi-x)*(yhi-y) + 
     +           wflohi*(xhi-x)*(y-ylo) + 
     +           wfhilo*(x-xlo)*(yhi-y) + 
     +           wfhihi*(x-xlo)*(y-ylo)
c
      wfinterp = wfinterp/area
c
c       return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                              subroutine arg                                  c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      real*8 function arg(x,y)
      implicit none
      real*8 x, y, pi
c
c This function computes the Arg(z) where z = x+i*y on the domain (-pi,pi] and 
c returns
c
c       define pi
c
      pi = 3.1415265358979d0
c
c       compute the Arg(x,y)
c
      if      ((x.eq.0.d0).AND.(y.lt.0.d0)) then
        arg = -1.d0*pi/2.d0
      else if ((x.eq.0.d0).AND.(y.gt.0.d0)) then
        arg = +3.d0*pi/2.d0
      else if ((x.lt.0.d0).AND.(y.eq.0.d0)) then
        arg = -2.d0*pi/2.d0
      else if ((x.ge.0.d0).AND.(y.eq.0.d0)) then
        arg = +0.d0*pi/2.d0
      else if ((x.lt.0.d0).AND.(y.lt.0.d0)) then
        arg = -2.d0*pi/2.d0 + datan(dabs(y/x))
      else if ((x.gt.0.d0).AND.(y.lt.0.d0)) then
        arg = -1.d0*pi/2.d0 + datan(dabs(x/y))
      else if ((x.gt.0.d0).AND.(y.gt.0.d0)) then
        arg = +0.d0*pi/2.d0 + datan(dabs(y/x))
      else if ((x.lt.0.d0).AND.(y.gt.0.d0)) then
        arg = +1.d0*pi/2.d0 + datan(dabs(x/y))
      else
        arg = 0.d0
      endif
c
c       return
c
      return
      end       
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                           subroutine LUXRF                                   c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine LUXRF(a_max,
     +                 real_or_imag,
     +                 Nx,
     +                 Ny,
     +                 dx,
     +                 dy,
     +                 dt,
     +                 x,
     +                 y,
     +                 with_diss,
     +                 gamma_diss,
     +                 omega_rf,
     +                 cPsi)
      implicit none
      integer*4 Nx, Ny, a_max, real_or_imag, with_diss, i, j
      real*8 dx, dy, dt, gamma_diss, omega_rf
      real*8 x(0:Nx), y(0:Ny)
      complex*16 ci, cdt
      complex*16 cPsi(0:a_max,0:a_max)
      complex*16 alpha(0:a_max), beta(0:a_max)
      complex*16 Am(0:a_max), A0(0:a_max), Ap(0:a_max)
      complex*16 gam(0:a_max), b(0:a_max)
c
c This routine applies the exp(-i*H2x*dt) to Psi_(k+1/3) to solve the 
c rotating-frame gross-pitaevskii equation.
c
c	define the ci=sqrt(-1)
c
      ci = (0.d0,1.d0)
c
c	test for imaginary (real_or_imag=0) or real time (real_or_imag=1)
c	propagation and define cdt appropriately
c
      if (real_or_imag.eq.0) then
        cdt = -ci*dt
      elseif (real_or_imag.eq.1) then
        if (with_diss.eq.1) then !if running with dissipation
          cdt = ((1.d0,0.d0) - gamma_diss*ci)*dt
        else
          cdt = (1.d0,0.d0)*dt
        endif
      else
        print *, "Error: compute_CN_coefficients"
        print *, "real_or_imag not set to zero or one, halting..."
        stop
      endif
c
c       begin loop over y (OpenMP parallelized across y-lines)
c
!$OMP PARALLEL DO PRIVATE(i,alpha,beta,Am,A0,Ap,gam,b) SCHEDULE(STATIC)
      do j = 0, Ny
c
c       define the values of Am, A0, and Ap
c
        do i = 0, Nx
          Am(i) = -ci*cdt/(2.d0*dx*dx) -
     +             0.25d0*omega_rf*y(j)*cdt/dx
c
          A0(i) = (1.d0,0.d0) + ci*cdt/(dx*dx)
c
          Ap(i) = -ci*cdt/(2.d0*dx*dx) +
     +             0.25d0*omega_rf*y(j)*cdt/dx
        enddo
c
c       compute the values of b(i,j)
c
        b(0)  = cPsi(0,j)  + (ci*cdt/(2.d0*dx*dx))*
     +          (cPsi(1,j) - 2.d0*cPsi(0,j)) -
     +          (0.25d0*omega_rf*y(j)*cdt/dx)*(cPsi(1,j))
c
        b(Nx) = cPsi(Nx,j) + (ci*cdt/(2.d0*dx*dx))*
     +          (-2.d0*cPsi(Nx,j) + cPsi(Nx-1,j)) -
     +          (0.25d0*omega_rf*y(j)*cdt/dx)*(-cPsi(Nx-1,j))
        do i = 1, Nx-1
          b(i)  = cPsi(i,j) + (ci*cdt/(2.d0*dx*dx))*
     +            (cPsi(i+1,j) - 2.d0*cPsi(i,j) + cPsi(i-1,j)) -
     +            (0.25d0*omega_rf*y(j)*cdt/dx)*
     +            (cPsi(i+1,j) - cPsi(i-1,j))
        enddo
c
c       do the backwards loop to compute alpha and beta
c
        alpha(Nx-1) = (0.d0,0.d0)
        beta(Nx-1)  = (0.d0,0.d0)
        do i = Nx-1, 1, -1
          gam(i)     = (-1.d0,0.d0)/(A0(i)+alpha(i)*Ap(i))
          alpha(i-1) = gam(i)*Am(i)
          beta(i-1)  = gam(i)*(Ap(i)*beta(i)-b(i))
        enddo
c
c       do the forwards loop to compute the new value of cPsi(i,j)
c
        cPsi(0,j) = (0.d0,0.d0)
        do i = 0, Nx-1
          cPsi(i+1,j) = alpha(i)*cPsi(i,j) + beta(i)
        enddo
c
c       set cPsi x right endpoint to zero
c
        cPsi(Nx,j) = (0.d0,0.d0)
c
c       end loop over y
c
      enddo
!$OMP END PARALLEL DO
c
c       return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                           subroutine LUYRF                                   c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine LUYRF(a_max,
     +                 real_or_imag,
     +                 Nx,
     +                 Ny,
     +                 dx,
     +                 dy,
     +                 dt,
     +                 x,
     +                 y,
     +                 with_diss,
     +                 gamma_diss,
     +                 omega_rf,
     +                 cPsi)
      implicit none
      integer*4 Nx, Ny, a_max, real_or_imag, with_diss, i, j
      real*8 dx, dy, dt, gamma_diss, omega_rf
      real*8 x(0:Nx), y(0:Ny)
      complex*16 ci, cdt
      complex*16 cPsi(0:a_max,0:a_max)
      complex*16 alpha(0:a_max), beta(0:a_max)
      complex*16 Am(0:a_max), A0(0:a_max), Ap(0:a_max)
      complex*16 gam(0:a_max), b(0:a_max)
c
c This routine applies the exp(-i*H2x*dt) to Psi_(k+1/3) to solve the 
c rotating-frame gross-pitaevskii equation.
c
c	define the ci=sqrt(-1)
c
      ci = (0.d0,1.d0)
c
c	test for imaginary (real_or_imag=0) or real time (real_or_imag=1)
c	propagation and define cdt appropriately
c
      if (real_or_imag.eq.0) then
        cdt = -ci*dt
      elseif (real_or_imag.eq.1) then
        if (with_diss.eq.1) then !if running with dissipation
          cdt = ((1.d0,0.d0) - gamma_diss*ci)*dt
        else
          cdt = (1.d0,0.d0)*dt
        endif
      else
        print *, "Error: compute_CN_coefficients"
        print *, "real_or_imag not set to zero or one, halting..."
        stop
      endif
c
c       begin loop over x (OpenMP parallelized across x-lines)
c
!$OMP PARALLEL DO PRIVATE(j,alpha,beta,Am,A0,Ap,gam,b) SCHEDULE(STATIC)
      do i = 0, Nx
c
c       define the values of Am, A0, and Ap
c
        do j = 0, Ny
          Am(j) = -ci*cdt/(2.d0*dy*dy) +
     +             0.25d0*omega_rf*x(i)*cdt/dy
c
          A0(j) = (1.d0,0.d0) + ci*cdt/(dy*dy)
c
          Ap(j) = -ci*cdt/(2.d0*dy*dy) -
     +             0.25d0*omega_rf*x(i)*cdt/dy
        enddo
c
c       compute the values of b(i,j)
c
        b(0)  = cPsi(i,0)  + (ci*cdt/(2.d0*dy*dy))*
     +          (cPsi(i,1) - 2.d0*cPsi(i,0)) +
     +          (0.25d0*omega_rf*x(i)*cdt/dy)*(cPsi(i,1))
c
        b(Ny) = cPsi(i,Ny) + (ci*cdt/(2.d0*dy*dy))*
     +          (-2.d0*cPsi(i,Ny) + cPsi(i,Ny-1)) +
     +          (0.25d0*omega_rf*x(i)*cdt/dy)*(-cPsi(i,Ny-1))
        do j = 1, Ny-1
          b(j)  = cPsi(i,j) + (ci*cdt/(2.d0*dy*dy))*
     +            (cPsi(i,j+1) - 2.d0*cPsi(i,j) + cPsi(i,j-1)) +
     +            (0.25d0*omega_rf*x(i)*cdt/dy)*
     +            (cPsi(i,j+1) - cPsi(i,j-1))
        enddo
c
c       do the backwards loop to compute alpha and beta
c
        alpha(Ny-1) = (0.d0,0.d0)
        beta(Ny-1)  = (0.d0,0.d0)
        do j = Ny-1, 1, -1
          gam(j)     = (-1.d0,0.d0)/(A0(j)+alpha(j)*Ap(j))
          alpha(j-1) = gam(j)*Am(j)
          beta(j-1)  = gam(j)*(Ap(j)*beta(j)-b(j))
        enddo
c
c       do the forwards loop to compute the new value of cPsi(i,j)
c
        cPsi(i,0) = (0.d0,0.d0)
        do j = 0, Ny-1
          cPsi(i,j+1) = alpha(j)*cPsi(i,j) + beta(j)
        enddo
c
c       set cPsi y right endpoint to zero
c
        cPsi(i,Ny) = (0.d0,0.d0)
c
c       end loop over x
c
      enddo
!$OMP END PARALLEL DO
c
c       return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                            subroutine LUX                                    c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine LUX(a_max,
     +               Nx,
     +               Ny,
     +               cA2x,
     +               cA2x0,
     +               calpha2x,
     +               cgamma2x,
     +               cPsi)
      implicit none
c
c This subroutine applies the exp(-i*H2x*dt) to Psi1 using the Crank-Nicolson
c implicit method.
c	begin: parameter declarations
      integer*4 Nx, Ny, a_max
      complex*16 cA2x, cA2x0
      complex*16 calpha2x(0:a_max),cgamma2x(0:a_max)
      complex*16 cPsi(0:a_max,0:a_max)
c	end: parameter declarations
      integer*4 i, j
      complex*16 cb2x
c	begin: openmp declarations
      integer*4 threadid, omp_get_thread_num
      complex*16 cbeta2x(0:a_max,0:11)
c	end: openmp declarations
c
c	begin openmp parallel directive
c
!$OMP PARALLEL PRIVATE(threadid,i,j,cb2x)
      threadid = OMP_GET_THREAD_NUM()
!$OMP DO SCHEDULE(STATIC)
c
c	begin loop over y
c
      do j = 0, Ny
c
c	initialize cbeta2x(Nx-1)
c
          cbeta2x(Nx,threadid) = cPsi(Nx,j)
c
c	begin backwards loop over x-grid to compute cb2x and cbeta2x
c
          do i = Nx-1, 1, -1
c
c	compute next cb2x
c
            cb2x = -cA2x*(cPsi(i+1,j)  -
     +               2.d0*cPsi(i,j)    +
     +                    cPsi(i-1,j)) +
     +                    cPsi(i,j)
c
c	compute next cbeta2x
c
            cbeta2x(i-1,threadid) = cgamma2x(i)*
     +                             (cA2x*cbeta2x(i,threadid)-cb2x)
c
c	end backwards loop over x-grid to compute cb2x and cbeta2x
c
          enddo
c
c	set cPsi x left endpoint to zero
c
          cPsi(0,j) = (0.d0,0.d0)
c
c	begin forward loop to update cPsi along x
c
          do i = 0, Nx-1
c
c	update cPsi at current point
c
            cPsi(i+1,j) = calpha2x(i)*cPsi(i,j) + 
     +                    cbeta2x(i,threadid)
c
c	end forward loop to update cPsi along x 
c
          enddo
c
c	set cPsi x right endpoint to zero
c
          cPsi(Nx,j) = (0.d0,0.d0)
c
c	end loop over y
c
      enddo
!$OMP END DO
!$OMP END PARALLEL
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                            subroutine LUY                                    c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine LUY(a_max,
     +               Nx,
     +               Ny,
     +               cA2y,
     +               cA2y0,
     +               calpha2y,
     +               cgamma2y,
     +               cPsi)
      implicit none
c
c This subroutine applies the exp(-i*H2y*dt) to Psi1 using the Crank-Nicolson
c implicit method.
c	begin: parameter declarations
      integer*4 Nx, Ny, a_max
      complex*16 cA2y, cA2y0
      complex*16 calpha2y(0:a_max), cgamma2y(0:a_max)
      complex*16 cPsi(0:a_max,0:a_max)
c	end: parameter declarations
      integer*4 i, j
      complex*16 cb2y
c	begin: openmp declarations
      integer*4 threadid, omp_get_thread_num
      complex*16 cbeta2y(0:a_max,0:11)
c	end: openmp declarations
c
c	begin openmp parallel directive
c
!$OMP PARALLEL PRIVATE(threadid,i,j,cb2y)
      threadid = OMP_GET_THREAD_NUM()
!$OMP DO SCHEDULE(STATIC)
c
c	begin loops over x and z
c
      do i = 0, Nx
c
c	initialize cbeta2y(Ny-1)
c
        cbeta2y(Ny,threadid) = cPsi(i,Ny)
c
c	begin backwards loop over y-grid to compute cb2y and cbeta2y
c
        do j = Ny-1, 1, -1
c
c	compute next cb2y
c
          cb2y = -cA2y*(cPsi(i,j+1)  -
     +             2.d0*cPsi(i,j)    +
     +                  cPsi(i,j-1)) +
     +                  cPsi(i,j)
c
c	compute next cbeta2y
c
          cbeta2y(j-1,threadid) = cgamma2y(j)*
     +                  (cA2y*cbeta2y(j,threadid)-cb2y)
c
c	end backwards loop over y-grid to compute cb2y and cbeta2y
c
        enddo
c
c	set cPsi y left endpoint to zero
c
        cPsi(i,0) = (0.d0,0.d0)
c
c	begin forward loop to update cPsi along y
c
        do j = 0, Ny-1
c
c	update cPsi at current point
c
          cPsi(i,j+1) = calpha2y(j)*cPsi(i,j) + 
     +                  cbeta2y(j,threadid)
c
c	end forward loop to update cPsi along y
c
        enddo
c
c	set cPsi y right endpoint to zero
c
        cPsi(i,Ny) = (0.d0,0.d0)
c
c	end loop over x
c
      enddo
!$OMP END DO
!$OMP END PARALLEL
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                        subroutine normalize_wf                               c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine normalize_wf(a_max,
     +                        Nx,
     +                        Ny,
     +                        dx,
     +                        dy,
     +                        cPsi)
      implicit none
c
c This subroutine normalizes the wavefunction.
c
c	begin: parameter declarations
      integer*4 Nx, Ny, a_max
      real*8 dx, dy
      complex*16 cPsi(0:a_max,0:a_max)
c	end: parameter declarations
      integer*4 i, j
      real*8 psi_norm
c
c	initialize norm
c
      psi_norm = 0.d0
c
c	begin loops to calculate the norm of cPsi
c       OpenMP: for CPU parallel execution
c       OpenACC: for GPU parallel execution (use -acc flag)
c
#ifdef USE_GPU
!$acc parallel loop collapse(2) reduction(+:psi_norm)
#else
!$OMP PARALLEL DO PRIVATE(i,j) REDUCTION(+:psi_norm)
#endif
      do i = 0, Nx
        do j = 0, Ny
          psi_norm = psi_norm + cPsi(i,j)*dconjg(cPsi(i,j))*dx*dy
        enddo
      enddo
#ifdef USE_GPU
!$acc end parallel loop
#else
!$OMP END PARALLEL DO
#endif
c
c	compute norm
c
      psi_norm = 1.d0/dsqrt(psi_norm)
c
c	begin loops to normalize cPsi
c
#ifdef USE_GPU
!$acc parallel loop collapse(2)
#else
!$OMP PARALLEL DO PRIVATE(i,j)
#endif
      do i = 0, Nx
        do j = 0, Ny
          cPsi(i,j) = psi_norm*cPsi(i,j)
        enddo
      enddo
#ifdef USE_GPU
!$acc end parallel loop
#else
!$OMP END PARALLEL DO
#endif
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                             subroutine NU                                    c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine NU(a_max,
     +              real_or_imag,
     +              ci,
     +              dt,
     +              V,
     +              g_bar,
     +              Natoms,
     +              Nx,
     +              Ny,
     +              cPsi)
      implicit none
c
c This subroutine applies exp(-i H_1 dt) to the current wave function.
c
c	begin: parameter declarations
      integer*4 real_or_imag, Nx, Ny, a_max
      real*8 dt, g_bar, Natoms
      real*8 V(0:a_max,0:a_max)
      complex*16 ci, cPsi(0:a_max,0:a_max)
c	end: parameter declarations
      integer*4 i, j
      real*8 H1
      complex*16 cdt
c
c	compute cdt for real or imaginary time propagation
c
      if (real_or_imag.eq.0) then
        cdt = -ci*dt
      else
        cdt = dt
      endif
c
c	begin loop to apply exp(-i H1 dt) to Psi
c       OpenMP: for CPU parallel execution
c       OpenACC: for GPU parallel execution (use -acc flag)
c
#ifdef USE_GPU
!$acc parallel loop collapse(2) private(H1)
#else
!$OMP PARALLEL DO PRIVATE(i,j,H1) SCHEDULE(DYNAMIC)
#endif
      do j = 0, Ny
        do i = 0, Nx
          H1 = V(i,j)+g_bar*Natoms*dreal(cPsi(i,j)*dconjg(cPsi(i,j)))
          cPsi(i,j) = cdexp(-ci*H1*cdt)*cPsi(i,j)
        enddo
      enddo
#ifdef USE_GPU
!$acc end parallel loop
#else
!$OMP END PARALLEL DO
#endif
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                        subroutine get_initial_wf                             c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine get_initial_wf(xc_array,
     +                          yc_array,
     +                          read_initial_wf,
     +                          real_or_imag,
     +                          a_max,
     +                          Nx,
     +                          Ny,
     +                          dx,
     +                          dy,
     +                          x,
     +                          y,
     +                          cPsi)
      implicit none
c
c This subroutine fills cPsi (GPE solution array) with the initial-state wave
c function.  It gets the initial-state wf either by reading a external data
c file named "initial_wf.dat" or by setting the initial state equal to a 3D
c gaussian of unit width.
c
c	begin: parameter declarations
      integer*4 read_initial_wf, real_or_imag, a_max, Nx, Ny
      real*8 dx, dy
      real*8 x(0:a_max), y(0:a_max)
      complex*16 cPsi(0:a_max,0:a_max)
c	end: parameter declarations
      real*8 WFR(0:a_max,0:a_max)
      real*8 WFI(0:a_max,0:a_max)
      real*8 pi
      integer*4 i, j
      real*8 xc_array, yc_array
c
c	define pi
c
      pi = 3.14159265358979d0
c
c	if both read_initial_wf and real_or_imag equal 0
c	fill with Gaussian initial state
c
      if (read_initial_wf.eq.0) then
c
c	fill grid arrays
c
        do i = 0, Nx
          x(i) = -0.5d0*dfloat(Nx)*dx + dfloat(i)*dx + xc_array
        enddo
c
        do j = 0, Ny
          y(j) = -0.5d0*dfloat(Ny)*dy + dfloat(j)*dy + yc_array
        enddo
c
c	fill cPsi with Gaussian initial state
c
        do i = 0, Nx
          do j = 0, Ny
              cPsi(i,j) = 
     +        exp(-0.5d0*((x(i)-xc_array)*(x(i)-xc_array) +
     +                    (y(j)-yc_array)*(y(j)-yc_array)))*
     +        (pi**(-0.5d0))
          enddo
        enddo
c
c	continue if-block
c
      else
c
c	otherwise read initial state in from "initial_wf.dat"
c
        open(unit=69,
     +       file="initial_wf.dat",
     +       status="unknown",
     +       form="unformatted")
c
c	read in wf
c
        print *, "begin read initial_wf.dat"
        read(69) x, y, WFR, WFI
        print *, "end read initial_wf.dat"
c
c	close "initial_wf.dat"
c
        close(69)
c
c	fill wf array
c
        do i = 0, Nx
          do j = 0, Ny
              cPsi(i,j) = dcmplx(WFR(i,j),WFI(i,j))
          enddo
        enddo
c
c	end if-block
c
      endif
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                    subroutine compute_CN_coefficients                        c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine compute_CN_coefficients(a_max,
     +                                   real_or_imag,
     +                                   Nx,
     +                                   Ny,
     +                                   dx,
     +                                   dy,
     +                                   dt,
     +                                   ci,
     +                                   cA2x,
     +                                   cA2x0,
     +                                   calpha2x,
     +                                   cgamma2x,
     +                                   cA2y,
     +                                   cA2y0,
     +                                   calpha2y,
     +                                   cgamma2y,
     +                                   cdtdx2,
     +                                   cdtdy2,
     +                                   with_diss,
     +                                   gamma_diss)
      implicit none
c
c This subroutine pre-computes some of the coefficients needed in the 
c Crank-Nicolson scheme for propagating the wave function to the next
c time step.
c
c	begin: parameter declarations
      integer*4 Nx, Ny, a_max, real_or_imag
      real*8 dx, dy, dt
      complex*16 ci                                    !square-root of -1
      complex*16 cA2x, cA2x0, cA2y, cA2y0
      complex*16 calpha2x(0:a_max), cgamma2x(0:a_max)
      complex*16 calpha2y(0:a_max), cgamma2y(0:a_max)
      complex*16 cdtdx2, cdtdy2
c	end: parameter declarations
      integer*4 i, j
      complex*16 cdt
cccc begin dissipation declarations cccc
      integer*4 with_diss
      real*8 gamma_diss
cccc end dissipation declarations cccc
c
c	define the ci=sqrt(-1)
c
      ci = (0.d0,1.d0)
c
c	test for imaginary (real_or_imag=0) or real time (real_or_imag=1)
c	propagation and define cdt appropriately
c
      if (real_or_imag.eq.0) then
        cdt = -ci*dt
      elseif (real_or_imag.eq.1) then
        if (with_diss.eq.1) then !if running with dissipation
          cdt = ((1.d0,0.d0) - gamma_diss*ci)*dt
        else
          cdt = (1.d0,0.d0)*dt
        endif
      else
        print *, "Error: compute_CN_coefficients"
        print *, "real_or_imag not to zero or one, halting..."
        stop
      endif
c
c	compute the timestep/spacestep^2 ratios
c
      cdtdx2 = cdt/(dx*dx)
      cdtdy2 = cdt/(dy*dy)
c
c	set the value of the x C-N tridiagonal coefficients
c
      cA2x  = -0.5d0*ci*cdtdx2
      cA2x0 = (1.d0,0.d0) + ci*cdtdx2
c
c	compute the x alpha and beta propagator coefficients
c
      calpha2x(Nx-1) = (0.d0,0.d0)
      cgamma2x(Nx-1) = -1.d0/cA2x0
c
      do i = Nx-1, 1, -1
        calpha2x(i-1) = cgamma2x(i)*cA2x
        cgamma2x(i-1) = -1.d0/(cA2x0+cA2x*calpha2x(i-1))
      enddo
c
c	set the value of the y C-N tridiagonal coefficients
c
      cA2y  = -0.5d0*ci*cdtdy2
      cA2y0 = (1.d0,0.d0) + ci*cdtdy2
c
c	compute the y alpha and beta propagator coefficients
c
      calpha2y(Ny-1) = (0.d0,0.d0)
      cgamma2y(Ny-1) = -1.d0/cA2y0
c
      do i = Ny-1, 1, -1
        calpha2y(i-1) = cgamma2y(i)*cA2y
        cgamma2y(i-1) = -1.d0/(cA2y0+cA2y*calpha2y(i-1))
      enddo
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                      subroutine read_general_inputs                          c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine read_general_inputs(Natoms,
     +                               Nx,
     +                               Ny,
     +                               dx,
     +                               dy,
     +                               g_bar,
     +                               Nt,
     +                               dt,
     +                               Nframes,
     +                               tfi,
     +                               tff,
     +                               L0,
     +                               real_or_imag,
     +                               read_initial_wf,
     +                               output_frames,
     +                               phase_imprint,
     +                               with_diss,
     +                               gamma_diss,
     +                               omega_rf,
     +                               diag_stride)
      implicit none
c
c This subroutine reads General Inputs for the SSCN GPE solver.  It reads
c the file "sscn_gpe_solver_general_inputs.dat" and returns these to the
c calling program.
c
c	begin: parameter declarations
      real*8 dx, dy, dz, dt, g_bar, tfi, tff, L0, Natoms
      integer*4 Nx, Ny, Nz, Nt, Nframes, real_or_imag, read_initial_wf
      integer*4 output_frames, phase_imprint, with_diss
      integer*4 diag_stride
      real*8 gamma_diss
c	end: parameter declarations
      integer*4 num_header_lines, num_comment_lines, i
      character*80 line
      real*8 omega_rf
c
c	set number of header and comment lines
c
      num_header_lines  = 6
      num_comment_lines = 6
c
c	open General Inputs file
c
      open(unit=10,
     +     file="rfgpe_2d_solver_general_inputs.dat",
     +     status="unknown")
c
c	read header lines
c
      do i = 1, num_header_lines
        read(10,*) line
      enddo
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read Natoms
c
      read(10,*) Natoms
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read Nx
c
      read(10,*) Nx
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read Ny
c
      read(10,*) Ny
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read dx
c
      read(10,*) dx
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read dy
c
      read(10,*) dy
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read g_bar
c
      read(10,*) g_bar
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read Nt
c
      read(10,*) Nt
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read dt
c
      read(10,*) dt
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read Nframes
c
      read(10,*) Nframes
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read tfi
c
      read(10,*) tfi
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read tff
c
      read(10,*) tff
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read L0
c
      read(10,*) L0
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read real_or_imag
c
      read(10,*) real_or_imag
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read read_initial_wf
c
      read(10,*) read_initial_wf
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read output_frames
c
      read(10,*) output_frames
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read phase_imprint
c
      read(10,*) phase_imprint
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read with_diss
c
      read(10,*) with_diss
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read gamma_diss
c
      read(10,*) gamma_diss
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read omega_rf
c
      read(10,*) omega_rf
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(10,*) line
      enddo
c
c	read diag_stride
c
      read(10,*) diag_stride
c
c	close General Inputs file
c
      close(10)
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                    c
c                        get_winding_number                          c
c                                                                    c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine get_winding_number(array_size,
     +                              xc0,
     +                              yc0,
     +                              rc0,
     +                              Nx,
     +                              Ny,
     +                              xc,
     +                              yc,
     +                              dx,
     +                              dy,
     +                              psir,
     +                              psii,
     +                              xc_array,
     +                              yc_array,
     +                              w)
      implicit none
      integer*4 array_size, Nx, Ny, Ns, is
      integer*4 kx, jy, ix, iy
      real*8 xc0, yc0, rc0, w, s, pi, smax, ds
      real*8 xc(0:array_size), yc(0:array_size)
      real*8 psir(0:array_size,0:array_size)
      real*8 psii(0:array_size,0:array_size)
      real*8 xm, xp, ym, yp, dx, dy
      real*8 xsc, ysc, finterp
      real*8 psirmm, psirmp, psirpm, psirpp
      real*8 psiimm, psiimp, psiipm, psiipp
      real*8 psir_int, psii_int, ss, cs
      real*8 psirxmm, psirxmp, psirxpm, psirxpp, psirx_int
      real*8 psirymm, psirymp, psirypm, psirypp, psiry_int
      real*8 psiixmm, psiixmp, psiixpm, psiixpp, psiix_int
      real*8 psiiymm, psiiymp, psiiypm, psiiypp, psiiy_int
      real*8 vx(0:50000), vy(0:50000)
      real*8 tc
      real*8 xc_array, yc_array
c
c       set the arc-length grid parameters
c
      pi   = 3.14159265358979d0
      smax = 2.d0*pi*rc0
      Ns   = 5000
      ds   = smax/dfloat(Ns)

c
c       compute the velocity x and y components
c       along the path
c
      do is = 0, Ns-1
c
c       set current arc length
c
        s = dfloat(is)*ds
c
c       compute the indexes for xs and ys
c
        xsc = xc0 + rc0*dcos(s/rc0)
        ysc = yc0 + rc0*dsin(s/rc0)
        kx = int((xsc-xc_array)/dx) + Nx/2
        jy = int((ysc-yc_array)/dy) + Ny/2
ccc        print *, xsc, xc(kx)
ccc        print *, ysc, yc(jy)
ccc        print *, (yc(iy), iy = 0, Ny)
ccc        pause
ccc        kx = int(xsc*(dfloat(Nx)/dx) + Nx/2)
ccc        jy = int(ysc*(dfloat(Ny)/dy) + Ny/2)
c
c       set the four points for bilinear interpolation
c
        xm = xc(kx)
        xp = xc(kx+1)
        ym = yc(jy)
        yp = yc(jy+1)
c
c       set the values of psir and psii at the corners
c
        psirmm = psir(kx,jy)
        psirmp = psir(kx,jy+1)
        psirpm = psir(kx+1,jy)
        psirpp = psir(kx+1,jy+1)
c
        psiimm = psii(kx,jy)
        psiimp = psii(kx,jy+1)
        psiipm = psii(kx+1,jy)
        psiipp = psii(kx+1,jy+1)
c
c       compute the interpolated values of psir and psii at
c       the point (xs,ys)
c
        psir_int = finterp(xsc,
     +                     ysc,
     +                     xm,
     +                     xp,
     +                     ym,
     +                     yp,
     +                     psirmm,
     +                     psirmp,
     +                     psirpm,
     +                     psirpp)
c
        psii_int = finterp(xsc,
     +                     ysc,
     +                     xm,
     +                     xp,
     +                     ym,
     +                     yp,
     +                     psiimm,
     +                     psiimp,
     +                     psiipm,
     +                     psiipp)

c
c       compute the interpolated values of 
c       psirx, psiry, psiix, psiiy
c
        psirxmm= (-1.d0*psir(kx+2,jy) + 8.d0*psir(kx+1,jy)
     +         -8.d0*psir(kx-1,jy) + 1.d0*psir(kx-2,jy))
     +         /(12.d0*dx)
c
        psirxmp= (-1.d0*psir(kx+2,jy+1) + 8.d0*psir(kx+1,jy+1)
     +         -8.d0*psir(kx-1,jy+1) + 1.d0*psir(kx-2,jy+1))
     +         /(12.d0*dx)
c
        psirxpm= (-1.d0*psir(kx+3,jy) + 8.d0*psir(kx+2,jy)
     +         -8.d0*psir(kx,jy) + 1.d0*psir(kx-1,jy))
     +         /(12.d0*dx)
c
        psirxpp= (-1.d0*psir(kx+3,jy+1) + 8.d0*psir(kx+2,jy+1)
     +         -8.d0*psir(kx,jy+1) + 1.d0*psir(kx-1,jy+1))
     +         /(12.d0*dx)
c
        psirx_int = finterp(xsc,
     +                      ysc,
     +                      xm,
     +                      xp,
     +                      ym,
     +                      yp,
     +                      psirxmm,
     +                      psirxmp,
     +                      psirxpm,
     +                      psirxpp)
cccc
        psirymm= (-1.d0*psir(kx,jy+2) + 8.d0*psir(kx,jy+1)
     +         -8.d0*psir(kx,jy-1) + 1.d0*psir(kx,jy-2))
     +         /(12.d0*dy)
c
        psirymp= (-1.d0*psir(kx,jy+3) + 8.d0*psir(kx,jy+2)
     +         -8.d0*psir(kx,jy) + 1.d0*psir(kx,jy-1))
     +         /(12.d0*dy)
c
        psirypm= (-1.d0*psir(kx+1,jy+2) + 8.d0*psir(kx+1,jy+1)
     +         -8.d0*psir(kx+1,jy-1) + 1.d0*psir(kx+1,jy-2))
     +         /(12.d0*dy)
c
        psirypp= (-1.d0*psir(kx+1,jy+3) + 8.d0*psir(kx+1,jy+2)
     +         -8.d0*psir(kx+1,jy) + 1.d0*psir(kx+1,jy-1))
     +         /(12.d0*dy)
c
        psiry_int = finterp(xsc,
     +                      ysc,
     +                      xm,
     +                      xp,
     +                      ym,
     +                      yp,
     +                      psirymm,
     +                      psirymp,
     +                      psirypm,
     +                      psirypp)
cccc
        psiixmm= (-1.d0*psii(kx+2,jy) + 8.d0*psii(kx+1,jy)
     +         -8.d0*psii(kx-1,jy) + 1.d0*psii(kx-2,jy))
     +         /(12.d0*dx)
c
        psiixmp= (-1.d0*psii(kx+2,jy+1) + 8.d0*psii(kx+1,jy+1)
     +         -8.d0*psii(kx-1,jy+1) + 1.d0*psii(kx-2,jy+1))
     +         /(12.d0*dx)
c
        psiixpm= (-1.d0*psii(kx+3,jy) + 8.d0*psii(kx+2,jy)
     +         -8.d0*psii(kx,jy) + 1.d0*psii(kx-1,jy))
     +         /(12.d0*dx)
c
        psiixpp= (-1.d0*psii(kx+3,jy+1) + 8.d0*psii(kx+2,jy+1)
     +         -8.d0*psii(kx,jy+1) + 1.d0*psii(kx-1,jy+1))
     +         /(12.d0*dx)
c
        psiix_int = finterp(xsc,
     +                      ysc,
     +                      xm,
     +                      xp,
     +                      ym,
     +                      yp,
     +                      psiixmm,
     +                      psiixmp,
     +                      psiixpm,
     +                      psiixpp)
cccc
        psiiymm= (-1.d0*psii(kx,jy+2) + 8.d0*psii(kx,jy+1)
     +         -8.d0*psii(kx,jy-1) + 1.d0*psii(kx,jy-2))
     +         /(12.d0*dy)

        psiiymp= (-1.d0*psii(kx,jy+3) + 8.d0*psii(kx,jy+2)
     +         -8.d0*psii(kx,jy) + 1.d0*psii(kx,jy-1))
     +         /(12.d0*dy)

        psiiypm= (-1.d0*psii(kx+1,jy+2) + 8.d0*psii(kx+1,jy+1)
     +         -8.d0*psii(kx+1,jy-1) + 1.d0*psii(kx+1,jy-2))
     +         /(12.d0*dy)

        psiiypp= (-1.d0*psii(kx+1,jy+3) + 8.d0*psii(kx+1,jy+2)
     +         -8.d0*psii(kx+1,jy) + 1.d0*psii(kx+1,jy-1))
     +         /(12.d0*dy)
c
        psiiy_int = finterp(xsc,
     +                      ysc,
     +                      xm,
     +                      xp,
     +                      ym,
     +                      yp,
     +                      psiiymm,
     +                      psiiymp,
     +                      psiiypm,
     +                      psiiypp)

c
        vx(is) = 2.d0*(psir_int*psiix_int-psii_int*psirx_int)/
     +           (psir_int*psir_int+psii_int*psii_int)
        vy(is) = 2.d0*(psir_int*psiiy_int-psii_int*psiry_int)/
     +           (psir_int*psir_int+psii_int*psii_int)
c
c       end loop over arc length
c
      enddo
c
c       print vx and vy for debug
c
ccc      print *, (vx(is), is = 0, 100)
ccc      print *, psir_int, psii_int
ccc      print *, psiix_int, psirx_int
ccc      pause
c
c       begin loop to compute the winding number
c
      w = 0.d0
      do is = 0, Ns
c
c       set current arc length
c
        s = dfloat(is)*ds
c
c       update w
c
        w = w + (-vx(is)*dsin(s/rc0) + vy(is)*dcos(s/rc0))*ds
c
c       end winding number loop
c
      enddo
c
c       compute final value of winding number
c
      w = w/(4.d0*pi)
c
c       return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                    c
c                      bilinear interpolation                        c
c                                                                    c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      real*8 function finterp(x,
     +                        y,
     +                        xm,
     +                        xp,
     +                        ym,
     +                        yp,
     +                        fmm,
     +                        fmp,
     +                        fpm,
     +                        fpp)
      implicit none
      real*8 x, y, xm, xp, ym, yp
      real*8 fmm, fmp, fpm, fpp, A
c
c This function computes the bilinearly interpolated value of a scalar
c function f(x,y) at a point (x,y) located in a 2D grid box as shown
c
c          (xm,yp) o                   o (xp,yp)
c
c
c                             o (x,y)
c
c
c
c          (xm,ym) o                   o (xp,ym)
c
c where the function is known at the four corners of the grid box.
c
c       compute the interpolated value of f(x,y)
c
      A = (xp-xm)*(yp-ym)
c
      finterp = ((xp-x)*(yp-y)*fmm +
     +           (xp-x)*(y-ym)*fmp + 
     +           (x-xm)*(yp-y)*fpm + 
     +           (x-xm)*(y-ym)*fpp)/A
c
c       return
c
      return
      end

cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                    c
c                             get_mu                                 c
c                                                                    c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine get_mu(a_max,
     +                  Nx,
     +                  Ny,
     +                  dx,
     +                  dy,
     +                  x,
     +                  y,
     +                  V,
     +                  cPsi,
     +                  g_bar,
     +                  Natoms,
     +                  mu)
      implicit none
      integer*4 a_max, Nx, Ny, ix, iy
      complex*16 cPsi(0:a_max,0:a_max)
      real*8 x(0:a_max), y(0:a_max)
      real*8 WF_R(0:a_max,0:a_max), WF_I(0:a_max,0:a_max)
      real*8 V(0:a_max,0:a_max)
      real*8 g_bar, Natoms, mu
      real*8 dx, dy
      real*8 kex_term, key_term, pot_term, int_term
      real*8 psixr, psixi, psiyr, psiyi
c
c This routine computes the chemical potential of the wf contained
c the cPsi array.
c
c
c       fill wf_r and wf_i arrays
c
      do ix = 0, Nx
        do iy = 0, Ny
          WF_R(ix,iy) = dreal(cPsi(ix,iy))
          WF_I(ix,iy) = dimag(cPsi(ix,iy))
        enddo
      enddo
c
c	initialize terms in the chemical potential
c
      kex_term = 0.d0
      key_term = 0.d0
      pot_term = 0.d0
      int_term = 0.d0
c
c	begin loops over space grid
c
      do ix = 4, NX-4
        do iy = 4, NY-4
c
c	update kex_term at current space point
c
          psixr = ( -3.d0*WF_R(ix+4,iy) +
     +              32.d0*WF_R(ix+3,iy) -
     +             168.d0*WF_R(ix+2,iy) +
     +             672.d0*WF_R(ix+1,iy) -
     +             672.d0*WF_R(ix-1,iy) +
     +             168.d0*WF_R(ix-2,iy) -
     +              32.d0*WF_R(ix-3,iy) +
     +               3.d0*WF_R(ix-4,iy))/(840.d0*dx)
c
          psixi = ( -3.d0*WF_I(ix+4,iy) +
     +              32.d0*WF_I(ix+3,iy) -
     +             168.d0*WF_I(ix+2,iy) +
     +             672.d0*WF_I(ix+1,iy) -
     +             672.d0*WF_I(ix-1,iy) +
     +             168.d0*WF_I(ix-2,iy) -
     +              32.d0*WF_I(ix-3,iy) +
     +               3.d0*WF_I(ix-4,iy))/(840.d0*dx)
c
          kex_term = kex_term + (psixr*psixr+psixi*psixi)*dx*dy
c
c	update key_term at current space point
c
          psiyr = ( -3.d0*WF_R(ix,iy+4) +
     +              32.d0*WF_R(ix,iy+3) -
     +             168.d0*WF_R(ix,iy+2) +
     +             672.d0*WF_R(ix,iy+1) -
     +             672.d0*WF_R(ix,iy-1) +
     +             168.d0*WF_R(ix,iy-2) -
     +              32.d0*WF_R(ix,iy-3) +
     +               3.d0*WF_R(ix,iy-4))/(840.d0*dx)
c
          psiyi = ( -3.d0*WF_I(ix,iy+4) +
     +              32.d0*WF_I(ix,iy+3) -
     +             168.d0*WF_I(ix,iy+2) +
     +             672.d0*WF_I(ix,iy+1) -
     +             672.d0*WF_I(ix,iy-1) +
     +             168.d0*WF_I(ix,iy-2) -
     +              32.d0*WF_I(ix,iy-3) +
     +               3.d0*WF_I(ix,iy-4))/(840.d0*dx)
c
          key_term = key_term + (psiyr*psiyr+psiyi*psiyi)*dx*dy
c
c	update pot_term at current space point
c
            pot_term = pot_term + 
     +                 V(ix,iy)*
     +                 (WF_R(ix,iy)*WF_R(ix,iy) + 
     +                  WF_I(ix,iy)*WF_I(ix,iy))*dx*dy
c
c	update int_term at current space point
c
            int_term = int_term + g_bar*Natoms*
     +      ((WF_R(ix,iy)*WF_R(ix,iy)+
     +        WF_I(ix,iy)*WF_I(ix,iy))**2.d0)*dx*dy
c
c	end loops over space grid
c
        enddo
      enddo
c
c	print out results
c
      mu = kex_term + 
     +     key_term + 
     +     pot_term +
     +     int_term
c
      print *, "kex_term = ", kex_term
      print *, "key_term = ", key_term
      print *, "pot_term = ", pot_term
      print *, "int_term = ", int_term
      print *, "mu       = ", kex_term +
     +                        key_term +
     +                        pot_term +
     +                        int_term
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                              c
c                                    ramp                                      c
c                                                                              c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      real*8 function ramp(tc_si,
     +                     tramp_si,
     +                     ton_si,
     +                     tpi_si)
      implicit none
      real*8 tc_si, tramp_si, ton_si, tpi_si
c
c This function computes the height of the barrier at the current time.
c
c
c       compute current barrier height
c
      if (tc_si.le.tpi_si) then
        ramp = 0.d0
      elseif ((tc_si.ge.0.0d0*tramp_si+tpi_si)
     +       .AND.
     +        (tc_si.lt.1.0d0*tramp_si+tpi_si)) then
        ramp = (tc_si-tpi_si)/tramp_si
      elseif ((tc_si.ge.1.0d0*tramp_si+tpi_si)
     +       .AND.
     +        (tc_si.lt.1.0d0*tramp_si+ton_si+tpi_si)) then
        ramp = 1.d0
      elseif ((tc_si.ge.1.0d0*tramp_si+ton_si+tpi_si)
     +       .AND.
     +        (tc_si.lt.2.0d0*tramp_si+ton_si+tpi_si)) then
        ramp = (tpi_si + 2.0d0*tramp_si + ton_si - tc_si)/tramp_si
      else
        ramp = 0.d0
      endif
c
c       return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                    c
c                     get_potential (OPTIMIZED)                      c
c                                                                    c
c   Optimizations:                                                   c
c   1. Precompute ramp_value once (same for all grid points)         c
c   2. Precompute center arrays once before loop                     c
c   3. Inline barrier calculation to reduce function call overhead   c
c   4. Early exit when barrier is turned off                         c
c                                                                    c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine get_potential(a_max,V0,a,wd,wr,n,R,
     +                         nrows,ncols,xc_array,yc_array,
     +                         wperp,wpara,Ubmax,tramp_si,
     +                         ton_si,tpi_si,trel_si,
     +                         Nx,Ny,x,y,tc,V,real_or_imag)
      implicit none
      real*8 V0, a, wd, wr, n, R
      real*8 wperp, wpara, Ubmax(1:100,1:100)
      real*8 xc_array, yc_array
      integer*4 nrows, ncols, Nx, Ny, a_max, ix, iy
      real*8 x(0:a_max), y(0:a_max)
      real*8 V(0:a_max,0:a_max)
      real*8 dtap, tc, tramp_si, ton_si
      real*8 tpi_si, trel_si
      integer*4 real_or_imag
c
c     Local variables for optimization
c
      real*8 ramp_value, barrier_val
      real*8 xc(1:100), yc(1:100)
      real*8 dx_val, dy_val, wperp2, wpara2
      integer*4 irow, icol
c
c This routine fills the potential array, V, with the double-target-array
c potential at time tc.
c
c     OPTIMIZATION 1: Check early exit condition
c     If barrier is turned off, set V=0 and return immediately
c
      if (tc.ge.tpi_si+2.d0*tramp_si+ton_si) then
#ifdef USE_GPU
!$acc parallel loop collapse(2)
#else
!$OMP PARALLEL DO PRIVATE(ix,iy) COLLAPSE(2) SCHEDULE(STATIC)
#endif
        do ix = 0, Nx
          do iy = 0, Ny
            V(ix,iy) = 0.d0
          enddo
        enddo
#ifdef USE_GPU
!$acc end parallel loop
#else
!$OMP END PARALLEL DO
#endif
        return
      endif
c
c     OPTIMIZATION 2: Precompute ramp_value once (same for all points)
c
      if (tc.le.tpi_si) then
        ramp_value = 0.d0
      elseif ((tc.ge.tpi_si).AND.(tc.lt.tramp_si+tpi_si)) then
        ramp_value = (tc-tpi_si)/tramp_si
      elseif ((tc.ge.tramp_si+tpi_si)
     +       .AND.(tc.lt.tramp_si+ton_si+tpi_si)) then
        ramp_value = 1.d0
      elseif ((tc.ge.tramp_si+ton_si+tpi_si)
     +       .AND.(tc.lt.2.d0*tramp_si+ton_si+tpi_si)) then
        ramp_value = (tpi_si + 2.d0*tramp_si + ton_si - tc)/tramp_si
      else
        ramp_value = 0.d0
      endif
c
c     Multiply by real_or_imag flag
c
      ramp_value = ramp_value * dfloat(real_or_imag)
c
c     OPTIMIZATION 3: Precompute center arrays once
c
      do icol = 1, ncols
        xc(icol) = xc_array + (icol-0.5d0*dfloat(ncols+1))*(3.d0*R)
      enddo
      do irow = 1, nrows
        yc(irow) = yc_array + (irow-0.5d0*dfloat(nrows+1))*(5.d0*R)
      enddo
c
c     Precompute squares for barrier calculation
c
      wperp2 = wperp*wperp
      wpara2 = wpara*wpara
c
c	begin loops over space grids
c       OpenMP: for CPU parallel execution
c       OpenACC: for GPU parallel execution (use -acc flag)
c
!$OMP PARALLEL DO PRIVATE(ix,iy,barrier_val,dx_val,dy_val,irow,icol)
      do ix = 0, Nx
        do iy = 0, Ny
          V(ix,iy) = dtap(V0,
     +                    a,
     +                    wd,
     +                    wr,
     +                    n,
     +                    R,
     +                    nrows,
     +                    ncols,
     +                    xc_array,
     +                    yc_array,
     +                    x(ix),
     +                    y(iy))
          if (ramp_value.gt.0.d0) then
            barrier_val = 0.d0
            do irow = 1, nrows
              do icol = 1, ncols
                dx_val = x(ix) - xc(icol)
                dy_val = y(iy) - yc(irow)
                barrier_val = barrier_val + Ubmax(irow,icol)*
     +               dexp(-dx_val*dx_val/wpara2)*
     +               dexp(-dy_val*dy_val/wperp2)
              enddo
            enddo
            V(ix,iy) = V(ix,iy) + barrier_val * ramp_value
          endif
        enddo
      enddo
#ifdef USE_GPU
!$acc end parallel loop
#else
!$OMP END PARALLEL DO
#endif
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                    c
c               double-target array barrier potential                c
c                                                                    c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      real*8 function dtap_barrier(xc_array,
     +                             yc_array,
     +                             R,
     +                             nrows,
     +                             ncols,
     +                             wperp,
     +                             wpara,
     +                             Ubc,
     +                             x,
     +                             y)
      implicit none
      real*8 xc_array, yc_array, wperp, wpara
      real*8 Ubc(1:100,1:100)
      real*8 x, y, R
      integer*4 nrows, ncols, icol, irow
      real*8 xc(1:100), yc(1:100)
c
c This function computes the barrier potential for an array of double-target
c potentials.
c
c	fill center arrays
c
      do icol = 1, ncols
        xc(icol) = xc_array + (icol-0.5d0*dfloat(ncols+1))*(3.d0*R)
      enddo
      do irow = 1, nrows
        yc(irow) = yc_array + (irow-0.5d0*dfloat(nrows+1))*(5.d0*R)
      enddo
c
c	initialize barrier potential
c
      dtap_barrier = 0.d0
c
c	begin loops over double-targets
c
      do irow = 1, nrows
        do icol = 1, ncols
c
c	update potential at current double-target
c
          dtap_barrier = dtap_barrier + Ubc(irow,icol)*
     +         dexp(-(x-xc(icol))*(x-xc(icol))/(wpara*wpara))*
     +         dexp(-(y-yc(irow))*(y-yc(irow))/(wperp*wperp))
c
c	end loops over double-targets
c
        enddo
      enddo
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                    c
c              double-target potential array potential               c
c                                                                    c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      real*8 function dtap(V0,
     +                     a,
     +                     wd,
     +                     wr,
     +                     n,
     +                     R,
     +                     nrows,
     +                     ncols,
     +                     xc_array,
     +                     yc_array,
     +                     x,
     +                     y)
!$acc routine seq
      implicit none
      real*8 V0, a, wd, wr, n, R, V, x, y
      real*8 xc_array, yc_array, dtp
      integer*4 nrows, ncols, irow, icol
      real*8 xc(1:100), yc(1:100)
c
c This function computes the potential of a double-target potential
c array.  The is an nrows by ncols array of double-target potentials
c where the center of the array is at (xc_array,yc_array_).
c
c	fill center arrays
c
      do icol = 1, ncols
        xc(icol) = xc_array + (icol-0.5d0*dfloat(ncols+1))*(3.d0*R)
      enddo
      do irow = 1, nrows
        yc(irow) = yc_array + (irow-0.5d0*dfloat(nrows+1))*(5.d0*R)
      enddo
c
c	compute potential at current point
c
      V = 0.d0
      do icol = 1, ncols
        do irow = 1, nrows
          V = V + dtp(V0,
     +                a,
     +                wd,
     +                wr,
     +                n,
     +                R,
     +                xc(icol),
     +                yc(irow),
     +                x,
     +                y)
        enddo
      enddo
c
c	subtract off potentials of other double targets
c
      dtap = V - (dfloat(nrows*ncols)-1.d0)*V0
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                    c
c                      double-target potential                       c
c                                                                    c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      real*8 function dtp(V0,
     +                    a,
     +                    wd,
     +                    wr,
     +                    n,
     +                    R,
     +                    xc,
     +                    yc,
     +                    x,
     +                    y)
!$acc routine seq
      implicit none
      real*8 V0, a, wd, wr, n, R, xc, yc, x, y
      real*8 step, rho1, rho2, xrc1, yrc1, xrc2, yrc2
      real*8 xside
c
c This routine computes the value of a double-target potential whose
c center is at (xc,yc) with parameters V0, a, wd, wr, and R.
c
c	define the centers of rings 1 and 2
c
      xrc1 = xc
      yrc1 = yc + R
      xrc2 = xc
      yrc2 = yc - R
c
c	compute xside, if xside > 0 then (x,y) is on
c	the ring 2 side, if xside < 0 the (x,y) is on
c	the ring 1 side
c
      xside = (x-xc)*(xrc1-xrc2)+(y-yc)*(yrc2-yrc1)
c
c	compute the value of the double-target potential
c
c     Note: When wd=0 (no inner disk), the disk term exp(-(rho/wd)^2n)
c     should be 0 (like exp(-infinity)=0), giving just the ring potential.
c
      rho1 = dsqrt((x-xrc1)*(x-xrc1)+(y-yrc1)*(y-yrc1))
      rho2 = dsqrt((x-xrc2)*(x-xrc2)+(y-yrc2)*(y-yrc2))
c
      if (xside.ne.0.d0) then
        if (wd.gt.0.d0) then
          dtp = V0*(1.d0-dexp(-(rho1/wd)**(2.d0*n))-
     +                   dexp(-((rho1-R)/wr)**(2.d0*n)))*
     +                   step(-xside) +
     +          V0*(1.d0-dexp(-(rho2/wd)**(2.d0*n))-
     +                   dexp(-((rho2-R)/wr)**(2.d0*n)))*
     +                   step(+xside)
        else
c         wd=0: no inner disk, just ring potential
          dtp = V0*(1.d0-dexp(-((rho1-R)/wr)**(2.d0*n)))*
     +                   step(-xside) +
     +          V0*(1.d0-dexp(-((rho2-R)/wr)**(2.d0*n)))*
     +                   step(+xside)
        endif
      else
        if (wd.gt.0.d0) then
          dtp = V0*(1.d0-dexp(-(rho1/wd)**(2.d0*n))-
     +                   dexp(-((rho1-R)/wr)**(2.d0*n)))
        else
c         wd=0: no inner disk, just ring potential
          dtp = V0*(1.d0-dexp(-((rho1-R)/wr)**(2.d0*n)))
        endif
      endif
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                    c
c                         step function                              c
c                                                                    c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      real*8 function step(x)
!$acc routine seq
      implicit none
      real*8 x
c
c This function implements the step function.
c
      if (x.le.0.d0) then 
        step = 0.d0
      elseif (x.gt.0.d0) then
        step = 1.d0
      else
        step = 0.d0
      endif
c
c	return
c
      return
      end
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
c                                                                    c
c                           get_dtap_inputs                          c
c                                                                    c
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
      subroutine get_dtap_inputs(V0,
     +                           a,
     +                           wd,
     +                           wr,
     +                           R,
     +                           n,
     +                           nrows,
     +                           ncols,
     +                           xc_array,
     +                           yc_array,
     +                           wperp,
     +                           wpara,
     +                           Ubmax,
     +                           tramp_si,
     +                           ton_si,
     +                           tpi_si,
     +                           trel_si)
      implicit none
      real*8 V0, a, wd, wr, R, n, xc_array, yc_array, wperp, wpara
      real*8 Ubmax(1:100,1:100), tramp_si, ton_si, tpi_si, trel_si
      integer*4 nrows, ncols
      integer*4 num_header_lines, num_comment_lines, i, j
      character*80 line
c
c This routine reads the file "dtap_inputs.dat" to the array and single
c target potential specifications.
c
c
c	set num_header_lines and num_comment_lines
c
      num_header_lines  = 5
      num_comment_lines = 6
c
c	open input file "dtap_inputs.dat"
c
      open(unit=11,
     +     file="dtap_inputs.dat",
     +     status="unknown")
c
c	read header lines
c
      do i = 1, num_header_lines
        read(11,*) line
      enddo
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read V0
c
      read(11,*) V0
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read a
c
      read(11,*) a
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read wd
c
      read(11,*) wd
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read wr
c
      read(11,*) wr
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read R
c
      read(11,*) R
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read n
c
      read(11,*) n
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read nrows
c
      read(11,*) nrows
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read ncols
c
      read(11,*) ncols
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read xc_array
c
      read(11,*) xc_array
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read yc_array
c
      read(11,*) yc_array
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read wperp
c
      read(11,*) wperp
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read wpara
c
      read(11,*) wpara
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read in Ubmax array
c
      do i = 1, nrows
        read(11,*) (Ubmax(i,j), j = 1, ncols)
      enddo
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read tramp_si
c
      read(11,*) tramp_si
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read ton_si
c
      read(11,*) ton_si
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read tpi_si
c
      read(11,*) tpi_si
c
c	read comment lines
c
      do i = 1, num_comment_lines
        read(11,*) line
      enddo
c
c	read trel_si
c
      read(11,*) trel_si
c
c	close input file
c
      close(11)
c
c	return
c
      return
      end

