'''
TODO: check if shema validate can be used
TODO: check if precaching function can be used
TODO: cached versions of software tomls to ~/.pype/software


'''
import os
import sys
import toml
import platform

from .formating import format

from .utils import (get_conf_file)
from .repos import (solve_dependecies)
from .. import logger

Logger = logger()

solve_dependecies()

PYPE_DEBUG = os.getenv("PYPE_DEBUG") is "1"

log = Logger.getLogger(__name__)


MAIN = {
    "preset_split": "..",
    "file_start": "pype-config",
    "representation": ".toml"
}


class Dict_to_obj(dict):
    """ Hiden class

    Converts `dict` dot string object with optional slicing metod

    Output:
        nested dotstring object for example: root.item.subitem.subitem_item
        also nested dict() for example: root["item"].subitem["subitem_item"]

    """
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    platform = platform.system().lower()

    def __init__(self, *args, **kwargs):
        self._to_obj(args or kwargs)

    # def format(self, *args, **kwargs):
    def _format(self, template="{template_string}", data=dict()):
        return format(template, data)

    def format(self, *args, **kwargs):
        args = args or kwargs
        data = dict()
        if args and isinstance(args, tuple):
            [data.update(d) for d in args]
        elif args:
            data = args
        else:
            data = None

        if data:
            self.update(data)

        temp_dict = self.copy()

        def iter_dict(data):
            for k, v in data.items():
                if isinstance(v, dict):
                    iter_dict(v)
                else:
                    data[k] = self._format(str(v), temp_dict)
            return data

        return self._obj(
            iter_dict(temp_dict)
        )

    def _to_obj(self, args):
        if isinstance(args, tuple):
            for arg in args:
                self._obj(arg)
        else:
            self._obj(args)

    def _obj(self, args):
        assert isinstance(args, dict), "`args` must be <dict>"
        for key, value in args.items():
            if isinstance(value, dict):
                if key not in "path":
                    value = Dict_to_obj(value)
                else:
                    value = value[self.platform]

            if not key.isupper():
                self[key] = value
                self.format

    def add_to_env_var(self, *args, **kwargs):

        if isinstance(args, tuple):
            for arg in args:
                self._env(arg)
        else:
            self._env(args)

    def _env(self, args):
        '''
        TODO:   read from root config info environment.including
                and implement here
        TODO:
        '''
        assert isinstance(args, dict), "`args` must be <dict>"
        for key, value in args.items():
            # print("=# _env1: ", key, value)
            if not value:
                continue
            # print("=# _env2: ", key, value)
            if isinstance(value, dict):
                value = self.add_to_env_var(value)

            # adding to env vars
            if key in self.including:
                if key in "PYTHONPATH":
                    # print("== paths: ", key, os.environ[key])
                    if not isinstance(value, list):
                        paths = os.pathsep.join(
                            os.environ[key].split(os.pathsep)
                            + str(value).split(os.pathsep)
                        )
                        os.environ[key] = paths
                        [sys.path.append(p) for p in paths.split(os.pathsep)]
                    else:
                        paths = os.pathsep.join(
                            os.environ[key].split(os.pathsep)
                            + [os.path.normpath(self._format(str(p), self))
                               for p in value]
                        )
                        os.environ[key] = paths
                        [sys.path.append(p) for p in paths.split(os.pathsep)]
                        # replacing env vars
                else:
                    if not isinstance(value, list):
                        os.environ[key] = os.pathsep.join(
                            str(value).split(os.pathsep) +
                            os.environ[key].split(os.pathsep)
                        )
                    else:
                        os.environ[key] = os.pathsep.join(
                            [os.path.normpath(self._format(str(p), self))
                             for p in value]
                            + os.environ[key].split(os.pathsep)
                        )
                        # replacing env vars
            elif key.isupper() and key not in self.including:
                if isinstance(value, list):
                    try:
                        paths = os.pathsep.join(
                            os.environ[key].split(os.pathsep)
                            + [os.path.normpath(self._format(str(p), self))
                               for p in value]
                        )
                    except KeyError:
                        paths = os.pathsep.join(
                            [os.path.normpath(self._format(str(p), self))
                             for p in value]
                        )
                    os.environ[key] = paths
                else:
                    if not len(str(value).split(":")) >= 2:
                        os.environ[key] = os.path.normpath(
                            self._format(str(value), self)
                        )
                    else:
                        os.environ[key] = self._format(str(value), self)


class Templates(Dict_to_obj):

    def __init__(self, *args, **kwargs):
        super(Templates, self).__init__(*args, **kwargs)

        try:
            self.templates_root = os.path.join(
                os.environ["PYPE_STUDIO_TEMPLATES"],
                "templates"
            )
        except KeyError:
            self.templates_root = os.path.join(
                os.environ["PYPE_SETUP_ROOT"],
                "studio",
                "studio-templates",
                "templates"
            )
        # get all toml templates in order
        self._get_template_files()
        self._get_templates_to_args()

    def update(self,  *args, **kwargs):
        '''Adding content to object

        Examples:
            - simple way by adding one arg: dict()
                ```python
                self.update({'one': 'one_string', 'two': 'two_string'})```

            - simple way by adding args: arg="string"
                ```python
                self.update(one='one_string', two='two_string')```

            - combined way of adding content: kwards
                ```python
                self.update(
                    one="one_string",
                    two="two_string",
                    three={
                        'one_in_three': 'one_in_three_string',
                        'two_in_three': 'two_in_three_string'
                    )```
        '''
        self._to_obj(kwargs or args)

    def _get_templates_to_args(self):
        ''' Populates all available configs from templates

        Returns:
            configs (obj): dot operator
        '''
        main_list = [t for t in self._templates
                     if t['type'] in "main"]
        self._distribute(main_list)

        base_list = [t for t in self._templates
                     if t['type'] in "base"]
        self._distribute(base_list)

        apps_list = [t for t in self._templates
                     if t['type'] in "apps"]
        self._distribute(apps_list)

        context_list = [t for t in self._templates
                        if t['type'] in "context"]
        self._distribute(context_list)

        # run trough environ and format values
        # with environ and self also os.path.normpath

        # treat software separatly from system as NUKE_PATH
        # if PYTHONPATH then os.pathsep
        # if PATH then os.pathsep
    def _distribute(self, template_list):
        data = dict()
        for t in template_list:
            content = self.toml_load(t['path'])
            file_name = os.path.split(t['path'])[1].split(".")[0]

            try:
                if "__storage__" in t['path']:
                    data["locations"].update(content)
                elif t['type'] in "context":
                    data[t["department"]].update(content)
                else:
                    data[t["department"]][file_name].update(content)
            except KeyError:
                if "__storage__" in t['path']:
                    data["locations"] = content
                elif t['type'] in "context":
                    data[t["department"]] = content
                else:
                    try:
                        data[t["department"]][file_name] = content
                    except KeyError:
                        data[t["department"]] = dict()
                        data[t["department"]][file_name] = content

        if t['type'] in ["main", "base"]:
            # adds to object as attribute
            self.update(data)
            # adds to environment variables
            self.add_to_env_var(data)

            # format environment variables
            self._format_env_vars()

        elif t['type'] in ["apps"]:
            self.update(data)

        elif t['type'] in ["context"]:
            self.update(data)

    def _format_env_vars(self):
        selected_keys = [k for k in list(os.environ.keys())
                         for i in self.filtering
                         if i in k]
        env_to_change = {k: v for k, v in os.environ.items()
                         if k in selected_keys}

        for k, v in env_to_change.items():
            if not len(v.split(":")) >= 2:
                os.environ[k] = os.path.normpath(
                    self._format(v, self)
                )
                # print("--path after", os.environ[k])
            else:
                os.environ[k] = self._format(v, self)

        # fix sys.path
        sys_paths = sys.path
        new_sys_paths = [os.path.normpath(self._format(p, self))
                         for p in sys_paths]
        sys.path = []
        [sys.path.append(p)
         for p in new_sys_paths
         if p not in sys.path
         if p is not '.']

    def _create_templ_item(self,
                           t_name=None,
                           t_type=None,
                           t_department=None,
                           t_preset=None
                           ):
        ''' Populates all available configs from templates

        Returns:
            configs (obj): dot operator
        '''
        t_root = os.path.join(self.templates_root, t_department)
        list_items = list()
        if not t_name:
            content = [f for f in os.listdir(t_root)
                       if not f.startswith(".")
                       if not os.path.isdir(
                os.path.join(t_root, f)
            )]
            for t in content:
                list_items.append(
                    self._create_templ_item(
                        t.replace(MAIN["representation"], ""),
                        t_type,
                        t_department
                    )
                )

        if list_items:
            return list_items
        else:
            t_file = get_conf_file(
                dir=t_root,
                root_file_name=t_name,
                preset_name=t_preset
            )
            if PYPE_DEBUG:
                log.info("_create_templ_item.t_root:"
                         " {} ".format(t_root))
                log.info("_create_templ_item.t_file:"
                         " {} ".format(t_file))

            return {
                "path": os.path.join(t_root, t_file),
                "department": t_department,
                "type": t_type
            }

    def _get_template_files(self):
        '''Gets all available templates from studio-templates

        Returns:
            self._templates (list): ordered list of file paths
                                       and department and type
        '''
        self.install_root = os.path.join(
            os.environ["PYPE_STUDIO_TEMPLATES"],
            "install"
        )
        file = get_conf_file(
            dir=self.install_root,
            root_file_name=MAIN["file_start"]
        )

        self._templates = list()
        for t in self.toml_load(
                os.path.join(
                    self.install_root, file
                ))['templates']:
            # print("template: ", t)
            if t['type'] in ["base", "main", "apps"]:
                try:
                    if t['order']:
                        for item in t['order']:
                            self._templates.append(
                                self._create_templ_item(
                                    item,
                                    t['type'],
                                    t['dir'],
                                    t['preset']
                                )
                            )
                except KeyError as error:
                    # print("// error: {}".format(error))
                    self._templates.extend(
                        self._create_templ_item(
                            None,
                            t['type'],
                            t['dir'],
                            t['preset']
                        )
                    )
                    pass
            else:
                self._templates.append(
                    self._create_templ_item(
                        t['file'],
                        t['type'],
                        t['dir'],
                        t['preset']
                    )
                )
        self._templates

        # insert environment setings into object root
        for k, v in self.toml_load(
                os.path.join(
                    self.install_root, file
                ))['environment'].items():
            self[k] = v

    def toml_load(self, path):
        return toml.load(path)

    def toml_dump(self, path, data):
        with open(path, "w+") as file:
            file.write(toml.dumps(data))
        return True