"""Portable Ridge margin inference with a discretized Gaussian error model."""
import math
import model


def validate(artifact):
    if artifact.get('kind') != 'ridge-gaussian-margin' or artifact.get('schemaVersion') != 1:
        raise ValueError('Unsupported margin artifact')
    names=artifact['featureNames']
    if not names or len(set(names)) != len(names): raise ValueError('Invalid feature names')
    for key in ('mean','scale','coefficients'):
        if len(artifact[key]) != len(names) or not all(model.finite(x) for x in artifact[key]):
            raise ValueError('Invalid margin dimensions or values')
    if not all(x>0 for x in artifact['scale']) or not model.finite(artifact['sigma']) or artifact['sigma']<=0 or not model.finite(artifact['intercept']):
        raise ValueError('Invalid scale, sigma or intercept')


def predict_margin(artifact, features):
    validate(artifact)
    x=model.feature_vector(features,artifact['featureNames'])
    result=artifact['intercept']+sum(w*(v-m)/s for v,m,s,w in zip(x,artifact['mean'],artifact['scale'],artifact['coefficients']))
    if not math.isfinite(result): raise ValueError('Margin inference overflow')
    return result


def handicap_probabilities(mu,sigma,home_handicap=0):
    """Home -3.5 covers when actual home-minus-away margin exceeds 3.5."""
    if not all(model.finite(x) for x in (mu,sigma,home_handicap)) or sigma<=0:
        raise ValueError('Finite parameters and positive sigma required')
    threshold=-home_handicap
    integer=threshold.is_integer() if isinstance(threshold,float) else True
    first_cover=math.floor(threshold)+1
    last_loss=math.ceil(threshold)-1
    def cdf(x): return .5*math.erfc(-(x-mu)/(sigma*math.sqrt(2)))
    loss=cdf(last_loss+.5)
    cover=.5*math.erfc((first_cover-.5-mu)/(sigma*math.sqrt(2)))
    push=max(0.0,1.0-cover-loss) if integer else 0.0
    total=cover+loss+push
    return {'cover':cover/total,'push':push/total,'loss':loss/total}


def predict_many(artifact,features):
    output=[]
    for row in features:
        p=handicap_probabilities(predict_margin(artifact,row),artifact['sigma'])
        output.append({'homeWin':p['cover'],'awayWin':p['loss'],'tie':p['push']})
    return output
