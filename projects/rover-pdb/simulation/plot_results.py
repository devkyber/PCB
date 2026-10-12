"""Plot saved ngspice waveforms. Run with numpy and matplotlib available."""
from pathlib import Path
import io
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from raw_results import RawCaseStore

HERE=Path(__file__).resolve().parent
R=HERE/'results'
raw=RawCaseStore(R)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
                     'axes.spines.top':False,'axes.spines.right':False,
                     'axes.grid':True,'grid.alpha':0.2,'savefig.dpi':180})
colors=['#126f9a','#d36b24','#654393']
def csv(name):
    return np.loadtxt(io.BytesIO(raw.read(name)),delimiter=',',skiprows=1)
def finish(fig,name,note):
    fig.text(.075,.018,note,ha='left',va='bottom',fontsize=9,color='#414b57')
    fig.savefig(R/(name+'.png'),bbox_inches='tight')
    fig.savefig(R/(name+'.pdf'),bbox_inches='tight')
    plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(11,4.4))
fig.subplots_adjust(top=.80,bottom=.25,wspace=.24)
fig.suptitle('A9 motor-enable switch: simulated opening response',fontsize=15,fontweight='bold',y=.98)
fig.text(.075,.87,'ngspice 46 | Actual resistor topology; assumed pin/wiring capacitance',fontsize=10)
for ax,cap,col in zip(axes,(100,1000),colors):
    d=csv(f'en_switch_{cap}pF')
    ax.plot((d[:,0]-3.0006e-3)*1e6,d[:,3],color=col,label=f'EN, {cap} pF')
    ax.axhline(.8,color='#555',ls='--',label='OFF threshold: 0.8 V')
    ax.set(xlim=(-5,220),ylim=(-.1,4.1),xlabel='Time after switch opens (us)',ylabel='EN voltage (V)')
    ax.legend(loc='upper right',fontsize=9)
finish(fig,'enable_switch','R15 = 100 kohm defines OFF. About 15.7 / 157 us to reach 0.8 V.\nCapacitance is a sensitivity assumption; neither value is a measured board parasitic.')

fig,axes=plt.subplots(1,2,figsize=(11,4.8))
fig.subplots_adjust(top=.81,bottom=.27,wspace=.25)
fig.suptitle('Fast local-VBAT collapse: external-network sensitivity',fontsize=15,fontweight='bold',y=.98)
fig.text(.075,.88,'SW1 ON | Local VBAT forced from 25.2 V to 0 V in 10 us | IC clamps omitted',fontsize=10)
for ax,cap,col in zip(axes,(100,1000),colors):
    d=csv(f'en_battery_fall_{cap}pF_10us')
    ax.plot((d[:,0]-1e-3)*1e6,d[:,2]-d[:,1],color=col,label=f'EN - VIN, {cap} pF')
    ax.axhline(.3,color='#a33',ls='--',label='VIN + 0.3 V comparison')
    ax.set(xlim=(7,65),ylim=(-.4,3.2),xlabel='Time from start of forced fall (us)',ylabel='EN minus VIN (V)')
    ax.legend(loc='upper right',fontsize=9)
finish(fig,'enable_collapse','The external network retains charge during an imposed rapid input collapse.\nThis is not normal battery-unplug prediction or a damage simulation. A 1 ms fall gives much smaller differences.')

fig,axes=plt.subplots(1,2,figsize=(11,5.0),sharey=True)
fig.subplots_adjust(top=.80,bottom=.29,wspace=.18)
fig.suptitle('Motor output capacitors under injected current',fontsize=15,fontweight='bold',y=.98)
fig.text(.075,.87,'Isolated capacitor bank only: no converter, load, motor model or reverse-current path',fontsize=10)
for ax,bank,title in zip(axes,('typical','screen'),('Typical estimate: 245.6 uF','Reduced-capacitance screen: 195.6 uF')):
    for amp,col in zip((.1,.5,1),colors):
        d=csv(f'regen_{bank}_{amp:g}A')
        ax.plot(d[:,0]*1e3,d[:,1],color=col,label=f'{amp:g} A return')
    ax.axhline(24,color='#888',ls='--',lw=1,label='24 V comparison marker')
    ax.axvspan(1,2.002,color='#126f9a',alpha=.07)
    ax.set(title=title,xlabel='Time (ms)',xlim=(.8,2.4),ylim=(21.9,27.7))
    ax.legend(fontsize=8,loc='upper left')
axes[0].set_ylabel('Capacitor-bank terminal voltage (V)')
finish(fig,'regeneration','Return pulse: 1 ms flat top, 1 us edges. Bulk series resistance: 30 mohm proxy.\n24 V is only a comparison marker, not a verified motor limit. Fixed capacitances approximate DC-bias behavior.\nThese plots show charge storage under assumed pulses; they do not validate the LMR51450 during regeneration.')
print('Created three PNG plots and their vector PDF copies.')
