"""Exact mathematical functions extracted from the pre-acquisition STEP0 method.

Requires NumPy; performs no file/device/controller operations. Frequencies are
cycles per complex output word in signed-low-real + j signed-high-imag convention.
The frozen project() returns NaN for an unavailable optional neighbor median;
strict_project() canonicalizes only that diagnostic to None, exposes availability,
and leaves the operative conditional descriptive floor unchanged. Neither floor
is an established confidence interval; IID assumptions were not verified.
"""
import math
import numpy as np

CHUNK_WORDS=16384
PRIMARY=(-.13,-.02)
MAIN=(-.04,.005)
POSITIVE=(-.29,-.24)

def scalar(value):return dict(real=float(value.real),imag=float(value.imag),amplitude=float(abs(value)))

def stats(values):return dict(min=float(np.min(values)),median=float(np.median(values)),max=float(np.max(values)))

def fold(value):return (value+.5)%1-.5

def summation(delta,n):
    delta=fold(delta)
    return n+0j if abs(delta)<1e-14 else np.expm1(2j*np.pi*delta*n)/np.expm1(2j*np.pi*delta)

def project(y,frequencies):
    n=len(y);t=np.arange(n);f=[0.]+list(frequencies)
    q=np.array([np.vdot(np.exp(2j*np.pi*v*t),y) for v in f])
    G=np.array([[summation(b-a,n) for b in f] for a in f])
    condition=float(np.linalg.cond(G));assert condition<1e6,'Unresolved joint spectral design'
    inverse=np.linalg.inv(G);c=inverse@q
    residual_energy=max(0,float(np.vdot(y,y).real-np.vdot(c,q).real))
    residual_power=residual_energy/n
    # Selected-line nuisance removed before neighboring projection diagnostics.
    nearby=[]
    for bin_offset in list(range(-24,-7))+list(range(8,25)):
        g=frequencies[0]+bin_offset/n
        if any(abs(fold(g-v))<4/n for v in f):continue
        r=np.vdot(np.exp(2j*np.pi*g*t),y)-sum(v*summation(a-g,n) for a,v in zip(f,c))
        nearby.append(abs(r)/n)
    iid=math.sqrt(residual_energy/(n-len(f))*max(0,float(inverse[1,1].real)))
    floor=max(iid,float(np.median(nearby)))
    return dict(primary=scalar(c[1]),coefficients=[scalar(v) for v in c],frequencies=list(frequencies),
        residual_power=residual_power,descriptive_floor_counts=floor,
        conditional_iid_LS_scale_counts=iid,median_neighbor_residual_projection_counts=float(np.median(nearby)),
        iid_assumptions_verified=False,joint_condition=condition)

def spectrum(chunks):
    window=np.hanning(CHUNK_WORDS)
    return np.abs(np.fft.fftshift(np.fft.fft((chunks-chunks.mean(axis=1,keepdims=True))*window,65536,axis=1),axes=1))/window.sum()

def refine(y,frequency):
    n=np.arange(len(y));w=np.hanning(len(y));z=(y-y.mean())*w
    lo,hi=frequency-1/65536,frequency+1/65536;r=(math.sqrt(5)-1)/2
    def score(f):return abs(np.vdot(np.exp(2j*np.pi*f*n),z))**2
    c,d=hi-r*(hi-lo),lo+r*(hi-lo);sc,sd=score(c),score(d)
    for _ in range(20):
        if sc>sd:hi,d,sd=d,c,sc;c=hi-r*(hi-lo);sc=score(c)
        else:lo,c,sc=c,d,sd;d=lo+r*(hi-lo);sd=score(d)
    return (lo+hi)/2

def analyse_ON(chunks):
    s=spectrum(chunks);axis=np.fft.fftshift(np.fft.fftfreq(65536));median=np.median(s,axis=0)
    def peak(gate):
        allowed=np.flatnonzero((axis>=gate[0])&(axis<=gate[1])&(abs(axis)>2/CHUNK_WORDS))
        index=allowed[np.argmax(median[allowed])]
        return float(axis[index]),float(median[index])
    primary,amplitude=peak(PRIMARY);main,_=peak(MAIN);positive,_=peak(POSITIVE)
    selected=[primary,main,positive]
    peaks=np.flatnonzero((median[1:-1]>median[:-2])&(median[1:-1]>=median[2:]))+1
    threshold=max(.5,6*float(np.median(median)))
    for index in sorted(peaks,key=lambda i:-median[i]):
        f=float(axis[index])
        if median[index]<threshold or abs(f)<4/CHUNK_WORDS:continue
        if all(abs(fold(f-g))>4/CHUNK_WORDS for g in selected):selected.append(f)
        if len(selected)==12:break
    rows=[]
    for index,y in enumerate(chunks):
        nearby=np.flatnonzero((axis>=max(PRIMARY[0],primary-.001))&(axis<=min(PRIMARY[1],primary+.001)))
        coarse=float(axis[nearby[np.argmax(s[index,nearby])]])
        f=refine(y,coarse);frequencies=[f]+selected[1:]
        row=project(y,frequencies);row.update(chunk=index,primary_mu=f)
        rows.append(row)
    peaks_out=[dict(mu=float(axis[i]),median_windowed_amplitude_counts=float(median[i])) for i in sorted(peaks,key=lambda i:-median[i])[:16]]
    return rows,dict(primary_window_anchor_mu=primary,primary_median_windowed_amplitude_counts=amplitude,
        joint_frequencies=selected,full_spectrum_top16=peaks_out,maximum_joint_lines=12,
        weaker_unresolved_or_time_varying_products_not_excluded=True)

def strict_project(y, frequencies):
    """Strict-JSON adapter; the unchanged frozen mathematical fit is above."""
    row = project(y, frequencies)
    n = len(y)
    f = [0.] + list(frequencies)
    count = sum(not any(abs(fold(frequencies[0] + offset/n - v)) < 4/n for v in f)
                for offset in list(range(-24,-7)) + list(range(8,25)))
    diagnostic = row['median_neighbor_residual_projection_counts']
    if count == 0:
        if not math.isnan(diagnostic):
            raise ValueError('Frozen missing-neighbor representation changed')
        row['median_neighbor_residual_projection_counts'] = None
    elif not math.isfinite(diagnostic):
        raise ValueError('Unexpected available-neighbor diagnostic')
    row['neighbor_diagnostic'] = dict(available=count>0, eligible_projection_bins=count,
        reason=None if count else 'All 34 candidate bins excluded by fitted-line proximity.')
    return row
