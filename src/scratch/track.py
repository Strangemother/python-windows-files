import main as run_main
from loop import run_loop


def main_alt():
    run_main.run((test, ))


def main():
    conf = ('F:\\', settings,)# test[1][0], )
    cbs = (conf, callback,)
    run_loop([cbs])


def callback(a):
    print('track.callback', a)
    #return False


def callback_many(a):
    print('track.callback_many', len(a))

settings = dict(
    callback_many=callback_many,
    ignore=[
        '*.pyc',
        '**/env/*',
        '.git/**/*',
        '.git/*',
        r'![.]git(\\|/)*.*'
    ]

)

test = (
    "C:\\",
    (
        ('track', settings,),
        #  ('copy', dict(
        #     dst='F:\\tmp2',
        #     sync=True,
        #     init_sync_to=False,
        #     init_sync_force=False,
        #     init_sync_back=True,
        #     init_sync_back_on=['size', 'modified'],
        #     init_sync_back_missing=True,
        #     ),
        # ),
    )
)

if __name__ == '__main__':
    main()
