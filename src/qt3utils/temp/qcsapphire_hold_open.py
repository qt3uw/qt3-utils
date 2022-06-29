import argparse
import pprint

import qcsapphire

parser = argparse.ArgumentParser(description='Options to hold open certain pulser channels')
parser.add_argument('port', type=str,
                    help='The name of the USB port to which the QCSapphire pulser is connected')
parser.add_argument('channels', type=str, nargs='+', help='list of channels you want to hold open')

parser.add_argument('--off', default = False, action='store_true', help='turns the channel off')
parser.add_argument('--report', default = False, action='store_true', help='report pulser settings at the end of operations')

args = parser.parse_args()

p = qcsapphire.Pulser(args.port)
#p.flush()

if args.off:
    p.system.state(0)
else:
    p.system.state(1)
    p.system.mode('normal')
    p.system.external.mode('disabled')

for chan in args.channels:
    if args.off:
        p.channel(chan).state(0)
    else:
        print(f'Holding open channel {chan}')
        p.channel(chan).width(0.99999*float(p.system.period()))
        p.channel(chan).cmode('normal')
        p.channel(chan).polarity('normal')
        p.channel(chan).output.amplitude(5.0)
        p.channel(chan).state(1)

if args.report:
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(p.report_global_settings())

    for chan in p.channel_names()[1:]:
        pp.pprint(f'channel {chan}')
        pp.pprint(p.report_channel_settings(chan))
