"""
Provides the class PatternCoordinator and a family of FeatureCoordinator classes.

PatternCoordinator creates a set of pattern generators whose parameters are
related in some way, as controlled by a subclass of FeatureCoordinator.
"""

import os
import math
import json

import param
from param.parameterized import ParamOverrides

from imagen.patterngenerator import PatternGenerator
from imagen.image import FileImage
from imagen import Gaussian, Composite, Selector, CompositeBase

import numbergen


class FeatureCoordinator(param.ParameterizedFunction):
    """
    A FeatureCoordinator modifies a supplied PatternGenerator.

    The modification can depend on the string pattern_label and
    pattern_number supplied, in order to coordinate a set of patterns
    of the same type with systematic differences.

    FeatureCoordinators that introduce randomness should be seeded
    with a value based on the supplied master_seed, so that an
    entire set of patterns can be controlled with the one master_seed
    value.

    Subclasses of this class can accept parameters provided in params.

    This superclass ensures a common interface across all
    FeatureCoordinator subclasses, which is necessary because they are
    usually stored in a list, with each item called the same way.
    """

    def __call__(self, pattern, pattern_label, pattern_number, master_seed, **params):
        """
        'pattern' is the PatternGenerator to be modified
        'pattern_label' is the name to be given to this PatternGenerator, used to select different behaviors
        'pattern_number' is an integer value distinguishing between multiple patterns with the same pattern_label
        'master_seed' is to be used for any random number generator seeds used for this pattern
        'params' consists of optional keyword-value pairs to be provided for subclasses' parameters
        """
        raise NotImplementedError



class XCoordinator(FeatureCoordinator):
    """
    Chooses a random value for the x coordinate, subject to the provided position_bound_x.
    """

    position_bound_x = param.Number(default=0.8,doc="""
        Left/rightmost position of the pattern center on the x axis.""")

    def __call__(self, pattern, pattern_label, pattern_number, master_seed, **params):
        p = ParamOverrides(self,params,allow_extra_keywords=True)
        pattern.x += numbergen.UniformRandom(lbound=-p.position_bound_x,ubound=p.position_bound_x,seed=master_seed+12+pattern_number)



class YCoordinator(FeatureCoordinator):
    """
    Chooses a random value for the y coordinate, subject to the provided position_bound_y.
    """

    position_bound_y = param.Number(default=0.8,doc="""
        Upper/lowermost position of the pattern center on the y axis.""")

    def __call__(self, pattern, pattern_label, pattern_number, master_seed, **params):
        p = ParamOverrides(self,params,allow_extra_keywords=True)
        pattern.y += numbergen.UniformRandom(lbound=-p.position_bound_y,ubound=p.position_bound_y,seed=master_seed+35+pattern_number)



class OrientationCoordinator(FeatureCoordinator):
    """
    Chooses a random orientation within the specified orientation_bound in each direction.
    """

    orientation_bound = param.Number(default=math.pi,doc="""
        Rotate pattern around the origin by at most orientation_bound radians (in both directions).""")

    def __call__(self, pattern, pattern_label, pattern_number, master_seed, **params):
        p = ParamOverrides(self,params,allow_extra_keywords=True)
        pattern.orientation = numbergen.UniformRandom(lbound=-p.orientation_bound,ubound=p.orientation_bound,seed=master_seed+21+pattern_number)



class PatternCoordinator(param.Parameterized):
    """
    Returns a set of coordinated PatternGenerators, named according to pattern_labels.

    The features to be modified are specified with the features_to_vary
    parameter. A feature is something coordinated between the
    PatternGenerators, either:

    a. one of the existing parameters of the PatternGenerators
       (such as size), or
    b. a variable from which values for one of the existing parameters
       can be calculated (such as a position offset between two
       PatternGenerators), or
    c. a value inherent to a particular existing image dataset
       (due to how the dataset was collected or generated).

    Each PatternGenerator is first instantiated with the supplied
    pattern_parameters, and then subclasses of FeatureCoordinator are
    applied sequentially to modify the specified or default parameter
    values of each PatternGenerator.
    """

    pattern_type = param.ClassSelector(PatternGenerator,default=Gaussian,is_instance=False,doc="""
        PatternGenerator type to be used.""")

    pattern_parameters = param.Dict(default={'size': 0.088388, 'aspect_ratio': 4.66667},doc="""
        Parameter values to be passed to the PatternGenerator specified in pattern_type.""")

    patterns_per_label = param.Integer(default=2,doc="""
        Number of patterns to generate and combine for a given label.""")

    features_to_vary = param.List(default=['xy','or'],class_=str,doc="""
        Stimulus features that the caller wishes to be varied, such as:
          :'xy': Position in x and y coordinates
          :'or': Orientation

        Subclasses and callers may extend this list to include any
        other features for which a coordinator has been defined in
        feature_coordinators.""")

    pattern_labels = param.List(default=['Input'],class_=str,bounds=(1,None),doc="""
        For each string in this list, a PatternGenerator of the
        requested pattern_type will be returned, with parameters whose
        values may depend on the string label supplied. For instance,
        if the list ["Pattern1","Pattern2"] is supplied, a metafeature
        function might inspect those pattern_labels and set parameters
        differently for Pattern1 and Pattern2, returning two different
        PatternGenerators with those pattern_labels.""")

    master_seed = param.Integer(default=0,doc="""
        Base seed for all pattern parameter values. Each numbered
        pattern on each of the various pattern_labels will normally
        use a different random seed, but all of these seeds should
        include this master_seed value, so that changing it will
        change all of the random pattern parameter streams.""")

    composite_type = param.ClassSelector(CompositeBase,default=Composite,is_instance=False,doc="""
        Class that combines the patterns_per_label individual patterns
        and creates a single combined pattern that it returns for a
        given label.  For instance, imagen.Composite can merge the
        individual patterns into a single pattern using a variety of
        operators like add or maximum, while imagen.Selector can
        choose one out of a given set of patterns.""")

    composite_parameters = param.Dict(default={},doc="""
        If present, these parameter values will be passed to the composite specified in composite_type.""")

    feature_coordinators = param.Dict(default={
        'xy': [XCoordinator,YCoordinator],
        'or': OrientationCoordinator},doc="""
        Mapping from the feature name (key) to the method(s) to be
        applied to the pattern generators.  The value can either be a
        single method or a list of methods.""")


    def _create_patterns(self, properties=None):
        """
        Return a list (of length patterns_per_label) of PatternGenerator instances.
        Should use pattern_type and pattern_parameters to create each pattern.

        properties is a dictionary, e.g. {'pattern_label':
        pattern_label}, which can be used to create PatternGenerators
        depending on the requested pattern_label
        """
        return [self.pattern_type(**self.pattern_parameters) for i in range(self.patterns_per_label)]


    def __init__(self,inherent_features={},**params):

        """
        If a dataset already and inherently includes certain features, a dictionary
        with feature-name:code-to-access-the-feature pairs should be supplied
        specifying how to select (e.g. from a set of images) the appropriate
        feature value.

        Any extra parameter values supplied here will be passed down to the
        feature_coordinators requested in features_to_vary.
        """
        p=ParamOverrides(self,params,allow_extra_keywords=True)

        super(PatternCoordinator, self).__init__(**p.param_keywords())

        self._feature_params = p.extra_keywords()

        self._inherent_features = inherent_features

        # And also, this key must be in feature_coordinators because _inherent_features
        # can have additional features such as i to support multiple images

        # TFALERT: Once spatial frequency (sf) is added, this will
        # cause warnings, because all image datasets will have a
        # spatial frequency inherent feature, but mostly we just
        # ignore that by having only a single size of DoG, which
        # discards all but a narrow range of sf.  So the dataset will
        # have sf inherently, but that won't be an error or even
        # worthy of a warning.
        if(len((set(self._inherent_features.keys()) - set(self.features_to_vary)) & set(self.feature_coordinators.keys()))):
            self.warning('Inherent feature present which is not requested in features')

        self._feature_coordinators_to_apply = []
        for feature, feature_coordinator in self.feature_coordinators.items():
            if feature in self.features_to_vary and feature not in self._inherent_features:
                # if it is a list, append each list item individually
                if isinstance(feature_coordinator,list):
                    for individual_feature_coordinator in feature_coordinator:
                        self._feature_coordinators_to_apply.append(individual_feature_coordinator)
                else:
                    self._feature_coordinators_to_apply.append(feature_coordinator)

    def __call__(self):
        coordinated_pattern_generators={}
        for pattern_label in self.pattern_labels:
            patterns=self._create_patterns({'pattern_label': pattern_label})

            # Apply _feature_coordinators_to_apply
            for i in range(len(patterns)):
                for fn in self._feature_coordinators_to_apply:
                    fn(patterns[i],pattern_label,i,self.master_seed,**self._feature_params)

            combined_patterns=self.composite_type(generators=patterns,**self.composite_parameters)
            coordinated_pattern_generators.update({pattern_label:combined_patterns})
        return coordinated_pattern_generators



class PatternCoordinatorImages(PatternCoordinator):
    pattern_type = param.ClassSelector(PatternGenerator,default=FileImage,is_instance=False)

    pattern_parameters = param.Dict(default={'size': 10})

    composite_type = param.ClassSelector(CompositeBase,default=Selector,is_instance=False)

    def __init__(self,dataset_name,**params):
        """
        dataset_name is the path to a JSON file (https://docs.python.org/2/library/json.html)
        containing a description for a dataset.

        Any extra parameter values supplied here will be passed down to the
        feature_coordinators requested in features_to_vary.

        The JSON file should contain the following entries:

            :'name': Name of the dataset (string, default=basename(dataset_name))
            :'length': Number of images in the dataset (integer, default=number of files in directory of dataset_name minus 1)
            :'description': Description of the dataset (string, default="")
            :'source': Citation of paper for which the dataset was created (string, default=name)
            :'filename_template': Path to the images with placeholders ({placeholder_name})
            for inherent features and the image number, e.g. "filename_template": "images/image{i}.png"
            (default={current_image}.jpg)
            :'inherent_features': Dictionary specifying how to access inherent features; value is used in eval().

            Currently, the label of the pattern generator
            ('pattern_label') as well as the image number
            ('current_image') are given as parameters to each callable
            supplied in inherent_features, where current_image varies
            from 0 to length-1 and pattern_label is one of the items
            of pattern_labels. (python code, default={'i': lambda params: '%02d' % (params['current_image']+1)}

            Example 1: Imagine having images without any inherent
            features named as follows: "images/image01.png",
            "images/image02.png" and so on. Then, filename_template:
            "images/image{i}.png" and "inherent_features":
            "{'i': lambda params: '%02d' % (params['current_image']+1)}"
            This replaces {i} in the template with the current image number + 1

            Example 2: Imagine having image pairs from a stereo webcam named as follows: "images/image01_left.png",
            "images/image01_right.png" and so on. If pattern_labels=['Left','Right'], then
            filename_template: "images/image{i}_{dy}" and
            "inherent_features": "{'i': lambda params: '%02d' % (params['current_image']+1),
                                   'dy':lambda params: 'left' if params['pattern_label']=='Left' else 'right'}"

            Here, additionally {dy} gets replaced by either 'left' if the pattern_label is 'Left' or 'right' otherwise
        """

        filename=param.resolve_path(dataset_name)
        filepath=os.path.dirname(filename)
        dataset=json.loads(open(filename).read())

        self.dataset_name=dataset.get('name', os.path.basename(dataset_name))
        length = len([ f for f in os.listdir(filepath) if os.path.isfile(os.path.join(filepath,f)) ]) - 1
        self.patterns_per_label=dataset.get('length', length)
        self.description=dataset.get('description', "")
        self.filename_template=dataset.get('filename_template', filepath+"/{i}.jpg")
        self.source=dataset.get('source', self.dataset_name)
        inherent_features=eval(dataset['inherent_features']) if 'inherent_features' in dataset else {'i': lambda params: '%02d' % (params['current_image']+1)}

        super(PatternCoordinatorImages, self).__init__(inherent_features,**params)


    def _generate_filenames(self, params):
        filenames = [self.filename_template]*self.patterns_per_label
        for feature in self._inherent_features:
            filenames = [filename.replace('{'+feature+'}', self._inherent_features[feature](params))
                                for filename,params['current_image'] in zip(filenames,list(range(self.patterns_per_label)))]
        return filenames


    def _create_patterns(self, properties):
        return [self.pattern_type(
                    filename=f,
                    cache_image=False,
                    **self.pattern_parameters)
                for f,i in zip(self._generate_filenames(properties),list(range(self.patterns_per_label)))]
